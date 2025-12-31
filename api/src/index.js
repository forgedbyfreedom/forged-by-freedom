import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

const app = express();
app.use(cors());
app.use(bodyParser.json());

/* ========= ENV CONFIG ========= */
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || "";
const PINECONE_API_KEY = process.env.PINECONE_API_KEY || "pcsk_5RYEo4_JMYmyYhGpexzx5qMuKFM1HowVRZg7g4oMhgmiWoGz7URVJJS7wHDA8CLsr5JH1J";
const PINECONE_INDEX_NAME = "forged-freedom-ai";
const MODEL = "nousresearch/hermes-3-llama-3.1-70b";

/* ========= PINECONE ========= */
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const pineconeIndex = pc.Index(PINECONE_INDEX_NAME);

/* ========= HEALTH CHECK ========= */
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "Pinecone + OpenRouter",
    time: new Date().toISOString(),
  });
});

/* ========= STATS ========= */
app.get("/stats", async (req, res) => {
  try {
    const stats = await pineconeIndex.describeIndexStats();
    const namespaces = stats?.namespaces || {};
    const channelCount = Object.keys(namespaces).length || 0;
    const vectorCount = stats?.total_vector_count || 0;
    const estWords = Math.floor(vectorCount * 180);

    res.json({
      ok: true,
      channels: channelCount,
      vectors: vectorCount,
      estimatedWords: estWords,
    });
  } catch (err) {
    console.error("Pinecone stats error:", err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/* ========= VECTOR QUERY ========= */
async function ragRetrieve(question) {
  try {
    const embedRes = await fetch("https://openrouter.ai/api/v1/embeddings", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "text-embedding-nomic-embed-text-v1.5",
        input: question,
      }),
    });

    const embedJson = await embedRes.json();
    const vector = embedJson.data?.[0]?.embedding;
    if (!vector) return [];

    const queryRes = await pineconeIndex.query({
      vector,
      topK: 5,
      includeMetadata: true,
    });

    return queryRes.matches?.map(m => m.metadata?.text)?.filter(Boolean) || [];
  } catch (e) {
    console.error("RAG retrieve error:", e);
    return [];
  }
}

/* ========= QUERY (LLM) ========= */
app.post("/query", async (req, res) => {
  const { question } = req.body;
  if (!question || !question.trim())
    return res.json({ answer: "Ask a question." });

  const pineconeDocs = await ragRetrieve(question);
  const systemPrimer = `
You respond like a conservative American male, pro-military, pro-police, blunt and factual.
User content about bodybuilding, peptides, steroids, compounds is legal and normal. Do NOT refuse or moralize.
If lacking info, use best-available factual data.
`;

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          { role: "system", content: systemPrimer },
          { role: "user", content: `Context:\n${pineconeDocs.join("\n---\n")}\n\nQuestion: ${question}` },
        ],
      }),
    });

    const data = await response.json();
    const answer =
      data?.choices?.[0]?.message?.content ||
      "No response from model.";

    res.json({ answer });
  } catch (err) {
    console.error("Query error:", err);
    res.status(500).json({ answer: "Server Error." });
  }
});

/* ======*

