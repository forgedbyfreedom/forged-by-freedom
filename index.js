import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

/* ================= ENV ================= */
const {
  OPENAI_API_KEY,
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT
} = process.env;

const CHAT_MODEL =
  OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
const EMBED_MODEL = "text-embedding-3-large";

/* ================= PINECONE ================= */
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const baseIndex = pc.Index("forged-freedom-ai");

/* ================= EXPRESS ================= */
const app = express();
app.use(cors());
app.use(bodyParser.json());

/* ================= EMBED ================= */
async function embed(text) {
  const r = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENAI_API_KEY}`,
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

/* ================= SCORING ================= */
function score(text, question) {
  const t = text.toLowerCase();
  const q = question.toLowerCase();

  let s = 0;
  if (q.includes("tren") && t.includes("tren")) s += 10;
  if (/(woman|women|female)/.test(t)) s += 3;
  if (/(viril|mascul|androgen|voice|clitor|irreversible)/.test(t)) s += 3;

  return s;
}

/* ================= STATUS ================= */
app.get("/status", async (_req, res) => {
  const stats = await baseIndex.describeIndexStats();
  res.json({
    status: "ok",
    model: CHAT_MODEL,
    embedModel: EMBED_MODEL,
    index: "forged-freedom-ai",
    namespaces: Object.keys(stats.namespaces || {}),
    time: new Date().toISOString()
  });
});

/* ================= ASK ================= */
app.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) {
    return res.json({ answer: "No question provided." });
  }

  try {
    const vector = await embed(question);

    const namespaces = [
      "",
      "default",
      "transcripts",
      "thinkbig_priority",
      "anabolic_bodybuilding_priority",
      "women_steroids"
    ];

    let matches = [];

    for (const ns of namespaces) {
      const idx = ns ? baseIndex.namespace(ns) : baseIndex;
      const r = await idx.query({
        vector,
        topK: 15,
        includeMetadata: true
      });
      if (r?.matches) matches.push(...r.matches);
    }

    /* ===== DEDUPE ===== */
    const seen = new Set();
    matches = matches.filter(m => {
      const key = m.id || m.metadata?.text;
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    /* ===== HARD COMPOUND GATE ===== */
    const qLower = question.toLowerCase();
    if (qLower.includes("tren")) {
      matches = matches.filter(m =>
        (m.metadata?.text || "").toLowerCase().includes("tren")
      );
    }

    if (matches.length === 0) {
      return res.json({
        answer:
          "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    /* ===== SCORE + SELECT ===== */
    const top = matches
      .map(m => ({
        ...m,
        relevance: score(m.metadata?.text || "", question)
      }))
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, 3);

    const answer = top
      .map(
        (m, i) =>
          `${i + 1}) "${m.metadata.text}" — ${m.metadata.speaker || "Unknown Speaker"}, ${m.metadata.podcast || "Unknown Podcast"}`
      )
      .join("\n\n");

    const sources = top.map(m => ({
      podcast: m.metadata.podcast || "Unknown Podcast",
      episode: m.metadata.episode || "Unknown Episode",
      speaker: m.metadata.speaker || "Unknown Speaker",
      quote: m.metadata.text
    }));

    res.json({ answer, sources });

  } catch (err) {
    res.json({
      answer: "Server error while querying Ask Coach Bryan.",
      error: err.message
    });
  }
});

/* ================= START ================= */
const serverPort = PORT || 5051;
app.listen(serverPort, () => {
  console.log(`[FBF] Ask Coach Bryan running on :${serverPort}`);
});
