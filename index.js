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

if (!OPENROUTER_API_KEY || !PINECONE_API_KEY) {
  console.error("❌ Missing required environment variables");
  process.exit(1);
}

const CHAT_MODEL = OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
const EMBED_MODEL = "text-embedding-3-large";

// ================= PINECONE =================
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index("forged-freedom-ai");

// Namespaces to search (order matters)
const SEARCH_NAMESPACES = [
  "thinkbig_priority",
  "anabolic_bodybuilding_priority",
  "women_steroids",
  "",
  "transcripts",
  "default"
];

// ================= EXPRESS =================
const app = express();
app.use(cors());
app.use(bodyParser.json());

// ================= UTIL =================
async function embedQuery(text) {
  const res = await fetch("https://openrouter.ai/api/v1/embeddings", {
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

  const json = await res.json();
  const vector = json?.data?.[0]?.embedding;

  if (!vector || !Array.isArray(vector)) {
    throw new Error("Embedding failed — no usable vector returned.");
  }

  return vector;
}

function scoreMatch(text, question) {
  const q = question.toLowerCase();
  const t = text.toLowerCase();
  let score = 0;

  if (q.includes("tren") && t.includes("tren")) score += 5;
  if (q.includes("women") && (t.includes("woman") || t.includes("female"))) score += 4;
  if (q.includes("viril") && t.match(/viril|voice|clitor|facial hair|irreversible/)) score += 5;

  // Penalize unrelated compounds
  if (t.includes("anavar") || t.includes("oxandrolone")) score -= 5;
  if (t.includes("tbol") || t.includes("turinabol")) score -= 5;

  return score;
}

// ================= HEALTH =================
app.get("/status", async (req, res) => {
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
    res.status(500).json({ status: "error", error: err.message });
  }
});

// ================= ASK =================
app.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.json({ answer: "No question provided." });

  try {
    const vector = await embedQuery(question);

    let allMatches = [];

    for (const ns of SEARCH_NAMESPACES) {
      const results = await index
        .namespace(ns)
        .query({
          vector,
          topK: 8,
          includeMetadata: true
        });

      if (results?.matches) {
        allMatches.push(...results.matches);
      }
    }

    // Deduplicate by ID
    const unique = Object.values(
      allMatches.reduce((acc, m) => {
        acc[m.id] = m;
        return acc;
      }, {})
    );

    // Score + filter
    const scored = unique
      .map(m => ({
        ...m,
        scoreBoost: scoreMatch(m.metadata?.text || "", question)
      }))
      .filter(m => m.scoreBoost > 0)
      .sort((a, b) => b.scoreBoost - a.scoreBoost)
      .slice(0, 3);

    if (!scored.length) {
      return res.json({
        answer: "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    const answer = scored
      .map((m, i) => {
        const md = m.metadata || {};
        return `${i + 1}) "${md.text}" — ${md.speaker || "Unknown Speaker"}, ${md.podcast || "Unknown Podcast"}`;
      })
      .join("\n\n");

    const sources = scored.map(m => ({
      podcast: m.metadata?.podcast || "Unknown Podcast",
      episode: m.metadata?.episode || "Unknown Episode",
      speaker: m.metadata?.speaker || "Unknown Speaker",
      quote: m.metadata?.text
    }));

    res.json({ answer, sources });

  } catch (err) {
    res.status(500).json({
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
