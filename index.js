import express from "express";
import cors from "cors";
import fetch from "node-fetch";

/* =======================
   APP SETUP
======================= */
const app = express();
app.use(cors());
app.use(express.json());

/* =======================
   ENV VARS (SANITIZED)
======================= */
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const PINECONE_API_KEY   = process.env.PINECONE_API_KEY;
const PINECONE_HOST_RAW  = process.env.PINECONE_HOST;
const PORT               = process.env.PORT || 5051;

if (!PINECONE_HOST_RAW) {
  throw new Error("PINECONE_HOST is not set");
}

/* 🔒 sanitize once */
const PINECONE_HOST = PINECONE_HOST_RAW.trim().replace(/\/$/, "");

const MODEL = "nousresearch/hermes-3-llama-3.1-8b";

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", async (req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    openRouterConfigured: !!OPENROUTER_API_KEY,
    pineconeConfigured: !!PINECONE_API_KEY,
    pineconeHost: PINECONE_HOST,
    model: MODEL,
    time: new Date().toISOString()
  });
});

/* =======================
   MAIN ASK ENDPOINT
======================= */
app.post("/ask", async (req, res) => {
  try {
    const question = req.body?.question?.trim();
    if (!question) {
      return res.status(400).json({ error: "No question provided" });
    }

    /* ---------- 1️⃣ EMBEDDING ---------- */
    const embRes = await fetch(
      "https://openrouter.ai/api/v1/embeddings",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: "text-embedding-3-large",
          input: question
        })
      }
    );

    const emb = await embRes.json();
    const vector = emb?.data?.[0]?.embedding;

    if (!vector) {
      throw new Error("Embedding failed");
    }

    /* ---------- 2️⃣ PINECONE QUERY ---------- */
    const pineconeUrl = `${PINECONE_HOST}/query`;

    console.log("PINECONE QUERY URL:", pineconeUrl);

    const pcRes = await fetch(pineconeUrl, {
      method: "POST",
      headers: {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        vector,
        topK: 6,
        includeMetadata: true
      })
    });

    const pc = await pcRes.json();
    const matches = pc?.matches || [];

    if (!matches.length) {
      return res.json({
        answer: "No relevant material found in the Forged by Freedom database."
      });
    }

    /* ---------- 3️⃣ CONTEXT BUILD ---------- */
    const context = matches
      .slice(0, 3)
      .map((m, i) => {
        const md = m.metadata || {};
        const text =
          md.text ||
          md.chunk ||
          md.content ||
          md.transcript ||
          "";

        return `SOURCE ${i + 1}\n${text.slice(0, 1200)}`;
      })
      .join("\n\n");

    /* ---------- 4️⃣ LLM COMPLETION --*
