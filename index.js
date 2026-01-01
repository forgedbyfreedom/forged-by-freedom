import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

// ========== ENV LOADING ==========
const {
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT
} = process.env;

// DEFAULT MODEL SAFETY
const MODEL = OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";

// ========== PINECONE ==========
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const pineconeIndex = pc.Index("forged-freedom-ai");

// ========== EXPRESS ==========
const app = express();
app.use(cors());
app.use(bodyParser.json());

// ===== HEALTH =====
app.get("/status", async (req, res) => {
  try {
    await pineconeIndex.describeIndexStats();
    res.json({
      status: "ok",
      openRouterConfigured: !!OPENROUTER_API_KEY,
      pineconeConfigured: !!PINECONE_API_KEY,
      model: MODEL,
      index: "forged-freedom-ai",
      backend: "root-index",
      pineconeConnected: true,
      time: new Date().toISOString()
    });
  } catch (err) {
    res.json({
      status: "error",
      pineconeConnected: false,
      model: MODEL,
      error: err.message
    });
  }
});

// ===== QUERY =====
app.post("/query", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.json({ answer: "No question provided" });

  try {
    // LLM call
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "HTTP-Referer": "https://www.forgedbyfreedom.org",
        "X-Title": "FBF AI Coach",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          { role: "user", content: question }
        ]
      })
    });

    const data = await response.json();

    if (!data?.choices) {
      return res.json({
        answer: "Server error — OpenRouter returned null response",
        error: JSON.stringify(data)
      });
    }

    const answer = data.choices[0].message.content;
    res.json({ answer });

  } catch (err) {
    res.json({
      answer: "Server error in AI Coach backend. If this keeps happening, ping Coach Bryan.",
      error: err.message
    });
  }
});

// ===== START =====
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF] running on :${SERVER_PORT} using model ${MODEL}`);
});

