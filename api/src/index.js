import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

const app = express();
app.use(cors());
app.use(bodyParser.json());

/* ======= OPENROUTER ======= */
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || "";
const MODEL = "nousresearch/hermes-3-llama-3.1-70b";

/* ======= PINECONE ======= */
const pc = new Pinecone({
  apiKey: process.env.PINECONE_API_KEY
});
const pineconeIndex = pc.Index("forged-freedom-ai");

/* ======= HEALTH ======= */
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "Pinecone + OpenRouter",
    time: new Date().toISOString()
  });
});

/* ======= STATS ======= */
app.get("/stats", async (req, res) => {
  try {
    const stats = await pineconeIndex.describeIndexStats();
    const vectorCount = stats?.total_vector_count || 0;
    const channels = Object.keys(stats?.namespaces || {}).length;
    const estWords = Math.floor(vectorCount * 175);

    res.json({ ok: true, channels, vectors: vectorCount, estimatedWords: estWords });

  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

/* ======= QUERY ======= */
app.post("/query", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.json({ answer: "⚠️ Empty question." });

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [{ role: "user", content: question }]
      })
    });

    const data = await response.json();
    const answer = data?.choices?.[0]?.message?.content || "⚠️ No response received.";

    res.json({ answer });

  } catch (err) {
    res.status(500).json({ answer: "❌ Server Error: " + err.message });
  }
});

/* ======= START ======= */
const PORT = process.env.PORT || 5051;
app.listen(PORT, () => console.log(`🔥 Forged By Freedom API running on ${PORT}`));

