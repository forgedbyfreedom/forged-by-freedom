import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

// ================= ENV =================
const {
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT
} = process.env;

const MODEL = OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
const EMBED_MODEL = "text-embedding-3-large";

// ================= INIT =================
const app = express();
app.use(cors());
app.use(bodyParser.json());

const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index("forged-freedom-ai");

// ================= HEALTH =================
app.get("/status", async (req, res) => {
  try {
    const stats = await index.describeIndexStats();
    res.json({
      status: "ok",
      model: MODEL,
      embedModel: EMBED_MODEL,
      index: "forged-freedom-ai",
      namespaces: Object.keys(stats.namespaces || {}),
      time: new Date().toISOString()
    });
  } catch (err) {
    res.status(500).json({
      status: "error",
      error: err.message
    });
  }
});

// ================= ASK =================
app.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) {
    return res.status(400).json({ answer: "No question provided." });
  }

  try {
    // ---------- OPENROUTER CALL ----------
    const orResponse = await fetch(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://www.forgedbyfreedom.org",
          "X-Title": "Ask Coach Bryan"
        },
        body: JSON.stringify({
          model: MODEL,
          messages: [{ role: "user", content: question }]
        })
      }
    );

    // ---------- LOG STATUS ----------
    console.log("[OpenRouter]", {
      status: orResponse.status,
      remaining: orResponse.headers.get("x-ratelimit-remaining"),
      reset: orResponse.headers.get("x-ratelimit-reset")
    });

    const payload = await orResponse.json();

    // ---------- HARD VALIDATION ----------
    if (
      !payload ||
      !Array.isArray(payload.choices) ||
      payload.choices.length === 0 ||
      !payload.choices[0]?.message?.content
    ) {
      console.error("[OpenRouter Invalid Payload]", payload);
      return res.status(502).json({
        answer: "AI provider returned an invalid response.",
        debug: payload
      });
    }

    return res.json({
      answer: payload.choices[0].message.content
    });

  } catch (err) {
    console.error("[Ask Error]", err);
    return res.status(500).json({
      answer: "Server error while querying Ask Coach Bryan.",
      error: err.message
    });
  }
});

// ================= START =================
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF] Ask Coach Bryan running on :${SERVER_PORT}`);
});
