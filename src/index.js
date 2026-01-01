import express from "express";
import cors from "cors";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

const app = express();

/* ============= MIDDLEWARE ============= */
app.use(
  cors({
    origin: "*",
    methods: ["GET", "POST", "OPTIONS"],
    allowedHeaders: ["Content-Type"],
  })
);
app.use(express.json());

/* ============= ENV VARS ============= */
// These MUST be set in Render environment (no hardcoding)
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || "";
const PINECONE_API_KEY = process.env.PINECONE_API_KEY || "";
const PINECONE_INDEX = process.env.PINECONE_INDEX || "forged-freedom-ai";

// Main model for answers
const MODEL = "nousresearch/hermes-3-llama-3.1-70b";

/* ============= PINECONE CLIENT ============= */
let pineconeIndex = null;

if (!PINECONE_API_KEY) {
  console.warn("[WARN] PINECONE_API_KEY is not set. /stats will fail.");
} else {
  try {
    const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
    pineconeIndex = pc.Index(PINECONE_INDEX);
    console.log(`[Pinecone] Using index: ${PINECONE_INDEX}`);
  } catch (err) {
    console.error("[Pinecone] Initialization error:", err.message);
  }
}

/* ============= HEALTH / STATUS ============= */
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "OpenRouter + Pinecone (stats only)",
    time: new Date().toISOString(),
  });
});

app.get("/status", (req, res) => {
  res.json({
    status: "ok",
    openRouterConfigured: !!OPENROUTER_API_KEY,
    pineconeConfigured: !!PINECONE_API_KEY,
    index: PINECONE_INDEX,
    time: new Date().toISOString(),
  });
});

/* ============= /stats (PINECONE) ============= */
app.get("/stats", async (req, res) => {
  if (!pineconeIndex) {
    return res.status(500).json({
      ok: false,
      error: "Pinecone not configured (missing API key or index).",
    });
  }

  try {
    const stats = await pineconeIndex.describeIndexStats();
    const namespaces = stats?.namespaces || {};
    const channels = Object.keys(namespaces).length || 0;
    const vectors = stats?.total_vector_count || 0;
    const estimatedWords = Math.floor(vectors * 175); // rough estimate

    res.json({ ok: true, channels, vectors, estimatedWords });
  } catch (err) {
    console.error("[/stats] Pinecone error:", err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/* ============= /query (OpenRouter) ============= */
app.post("/query", async (req, res) => {
  const { question } = req.body || {};

  if (!question || !question.trim()) {
    return res.json({ answer: "Please enter a question." });
  }

  if (!OPENROUTER_API_KEY) {
    console.error("[/query] Missing OPENROUTER_API_KEY");
    return res.status(500).json({
      answer: "Server misconfigured: missing OpenRouter API key.",
    });
  }

  const systemPrompt = `
You are an experienced strength training, bodybuilding, and nutrition coach.
You give detailed, factual, practical answers about training, diet, recovery, and performance.
You are direct and concise. You do not ramble or lecture.
You remind users that any drug, hormone, or enhancement strategy carries risks and that medical decisions should be made with a qualified professional.
  `.trim();

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
          { role: "system", content: systemPrompt },
          { role: "user", content: question },
        ],
      }),
    });

    const data = await response.json();

    if (!data || !data.choices || !data.choices[0]?.message?.content) {
      console.error("[/query] Unexpected OpenRouter response:", data);
      return res.json({
        answer: "No response available from the model at this time.",
      });
    }

    const answer = data.choices[0].message.content;
    res.json({ answer });
  } catch (err) {
    console.error("[/query] Error:", err);
    res.status(500).json({ answer: "Server error processing your request." });
  }
});

/* ============= START SERVER ============= */
const PORT = process.env.PORT || 5051;
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});

