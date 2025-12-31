import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

const app = express();
app.use(cors());
app.use(bodyParser.json());

/* ======= OPENROUTER BACKEND HANDLER ======= */
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || "";   // already set externally
const MODEL = "nousresearch/hermes-3-llama-3.1-70b";

/* ======= PINECONE CONNECTION ======= */
const pc = new Pinecone({
  apiKey: "pcsk_5RYEo4_JMYmyYhGpexzx5qMuKFM1HowVRZg7g4oMhgmiWoGz7URVJJS7wHDA8CLsr5JH1J"
});

const pineconeIndex = pc.Index("forged-freedom-ai");

/* ======= HEALTH CHECK ======= */
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "Pinecone + OpenRouter",
    time: new Date().toISOString()
  });
});

/* ======= /stats ENDPOINT ======= */
app.get("/stats", async (req, res) => {
  try {
    const stats = await pineconeIndex.describeIndexStats();

    const namespaces = stats?.namespaces || {};
    const channelCount = Object.keys(namespaces).length || 0;
    const vectorCount = stats?.total_vector_count || 0;

    // Estimation (later replaced with metadata true word count)
    const estWords = Math.floor(vectorCount * 180);

    res.json({
      ok: true,
      channels: channelCount,
      vectors: vectorCount,
      estimatedWords: estWords
    });
  } catch (err) {
    console.error("Pinecone stats error:", err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/* ======= /query ENDPOINT ======= */
app.post("/query", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.json({ answer: "Empty question." });

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
    const answer =
      data?.choices?.[0]?.message?.content ||
      data?.response ||
      "No response from model.";

    return res.json({ answer });
  } catch (err) {
    console.error("Query error:", err);
    res.status(500).json({ answer: "Server Error." });
  }
});

/* ======= START SERVER ======= */
const PORT = process.env.PORT || 5051;
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});
