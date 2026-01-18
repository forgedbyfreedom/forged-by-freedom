import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

/* =========================
   ENV
========================= */
const {
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT
} = process.env;

const CHAT_MODEL = OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
const EMBED_MODEL = "text-embedding-3-large";

/* =========================
   PINECONE
========================= */
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index("forged-freedom-ai");

/* =========================
   EXPRESS
========================= */
const app = express();
app.use(cors());
app.use(bodyParser.json());

/* =========================
   STATUS
========================= */
app.get("/status", async (_req, res) => {
  try {
    const stats = await index.describeIndexStats();
    res.json({
      status: "ok",
      model: CHAT_MODEL,
      embedModel: EMBED_MODEL,
      index: "forged-freedom-ai",
      namespaces: Object.keys(stats.namespaces || {}),
      time: new Date().toISOString()
    });
  } catch (err) {
    res.json({ status: "error", error: err.message });
  }
});

/* =========================
   HELPERS
========================= */
async function embedQuery(text) {
  const r = await fetch("https://openrouter.ai/api/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENROUTER_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: EMBED_MODEL,
      input: text
    })
  });

  const j = await r.json();
  if (!j?.data?.[0]?.embedding) {
    throw new Error("Embedding failed");
  }
  return j.data[0].embedding;
}

async function queryPinecone(vector) {
  const results = await index.query({
    vector,
    topK: 12,
    includeMetadata: true
  });

  return results.matches || [];
}

/* =========================
   ASK
========================= */
app.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) {
    return res.json({ answer: "No question provided.", sources: [] });
  }

  try {
    /* ---- 1. Embed question ---- */
    const vector = await embedQuery(question);

    /* ---- 2. Query Pinecone ---- */
    const matches = await queryPinecone(vector);

    if (!matches.length) {
      return res.json({
        answer: "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    /* ---- 3. Build context ---- */
    const context = matches
      .map((m, i) => {
        const md = m.metadata || {};
        return `[${i + 1}]
Podcast: ${md.podcast || "Unknown Podcast"}
Episode: ${md.episode || "Unknown Episode"}
Speaker: ${md.speaker || "Unknown Speaker"}
Quote: "${md.text || ""}"`;
      })
      .join("\n\n");

    /* ---- 4. Ask LLM with context ---- */
    const llm = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://www.forgedbyfreedom.org",
        "X-Title": "Ask Coach Bryan"
      },
      body: JSON.stringify({
        model: CHAT_MODEL,
        messages: [
          {
            role: "system",
            content:
              "Answer using the provided transcript excerpts. Cite quotes directly when relevant."
          },
          {
            role: "user",
            content: `QUESTION:\n${question}\n\nTRANSCRIPTS:\n${context}`
          }
        ]
      })
    });

    const llmJson = await llm.json();
    const answer = llmJson?.choices?.[0]?.message?.content;

    res.json({
      answer: answer || "No answer generated.",
      sources: matches.map(m => m.metadata || {})
    });
  } catch (err) {
    res.json({
      answer: "Server error while querying Ask Coach Bryan.",
      error: err.message
    });
  }
});

/* =========================
   START
========================= */
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF] Ask Coach Bryan running on :${SERVER_PORT}`);
});
