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

// ================= SIMPLE RATE LIMIT =================
// max 10 requests per IP per minute
const RATE_LIMIT_WINDOW = 60_000;
const RATE_LIMIT_MAX = 10;
const rateBuckets = new Map();

// ================= SINGLE-FLIGHT LOCK =================
const activeRequests = new Set();

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
  const ip = req.ip;

  // ----- RATE LIMIT -----
  const now = Date.now();
  const bucket = rateBuckets.get(ip) || [];
  const fresh = bucket.filter(ts => now - ts < RATE_LIMIT_WINDOW);

  if (fresh.length >= RATE_LIMIT_MAX) {
    return res.status(429).json({
      answer: "Too many requests. Please wait a moment and try again."
    });
  }

  fresh.push(now);
  rateBuckets.set(ip, fresh);

  // ----- SINGLE FLIGHT -----
  if (activeRequests.has(ip)) {
    return res.status(429).json({
      answer: "Please wait — your previous question is still processing."
    });
  }

  activeRequests.add(ip);

  try {
    const { question } = req.body;
    if (!question) {
      return res.status(400).json({ answer: "No question provided." });
    }

    // ----- OPENROUTER CALL -----
    const response = await fetch(
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

    console.log("[OpenRouter]", {
      status: response.status,
      remaining: response.headers.get("x-ratelimit-remaining")
    });

    const data = await response.json();

    if (!data?.choices?.[0]?.message?.content) {
      console.error("[Invalid OpenRouter Payload]", data);
      return res.status(502).json({
        answer: "AI provider returned an invalid response."
      });
    }

    return res.json({
      answer: data.choices[0].message.content
    });

  } catch (err) {
    console.error("[Ask Error]", err);
    return res.status(500).json({
      answer: "Server error while querying Ask Coach Bryan."
    });
  } finally {
    activeRequests.delete(ip);
  }
});

// ================= START =================
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF] Ask Coach Bryan running on :${SERVER_PORT}`);
});
