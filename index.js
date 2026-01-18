import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

/* ================== ENV ================== */
const {
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT
} = process.env;

const MODEL = OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
const EMBED_MODEL = "text-embedding-3-large";

/* ================== PINECONE ================== */
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index("forged-freedom-ai");

/* ================== APP ================== */
const app = express();
app.use(cors());
app.use(bodyParser.json());

/* ================== HEALTH ================== */
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
    res.json({ status: "error", error: err.message });
  }
});

/* ================== HELPERS ================== */
function scoreQuote(text, question) {
  const q = question.toLowerCase();
  const t = text.toLowerCase();
  let score = 0;

  if (q.includes("tren") && t.includes("tren")) score += 5;
  if ((q.includes("women") || q.includes("female")) &&
      (t.includes("women") || t.includes("female"))) score += 5;

  if (
    q.includes("viril") &&
    (t.includes("viril") ||
     t.includes("voice") ||
     t.includes("clitoral") ||
     t.includes("irreversible"))
  ) score += 5;

  return score;
}

/* ================== ASK ================== */
app.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) {
    return res.json({ answer: "No question provided." });
  }

  try {
    /* ---------- EMBED QUESTION ---------- */
    const embedResp = await fetch("https://openrouter.ai/api/v1/embeddings", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: EMBED_MODEL,
        input: question
      })
    });

    const embedData = await embedResp.json();
    const vector =
      embedData?.data?.[0]?.embedding ||
      embedData?.data?.[0]?.vector;

    if (!vector) {
      return res.json({
        answer: "Embedding failed — no usable vector returned.",
        debug: embedData
      });
    }

    /* ---------- QUERY MULTIPLE NAMESPACES ---------- */
    const namespaces = [
      "thinkbig_priority",
      "anabolic_bodybuilding_priority",
      "default",
      "transcripts",
      "" // legacy unnamed namespace
    ];

    let matches = [];

    for (const ns of namespaces) {
      const result = await index.query({
        vector,
        topK: 10,
        includeMetadata: true,
        namespace: ns
      });
      if (result?.matches?.length) {
        matches.push(...result.matches);
      }
    }

    if (!matches.length) {
      return res.json({
        answer: "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    /* ---------- SCORE + FILTER ---------- */
    const scored = matches
      .map(m => ({
        score: scoreQuote(m.metadata?.text || "", question),
        meta: m.metadata
      }))
      .filter(x => x.score > 0);

    if (!scored.length) {
      return res.json({
        answer: "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    scored.sort((a, b) => b.score - a.score);
    const top = scored.slice(0, 3);

    /* ---------- FORMAT RESPONSE ---------- */
    const quotes = top.map((x, i) => {
      const m = x.meta;
      return `${i + 1}) "${m.text}"
— ${m.speaker || "Unknown Speaker"}, ${m.podcast || "Unknown Podcast"}`;
    });

    const sources = top.map(x => ({
      podcast: x.meta.podcast || "Unknown Podcast",
      episode: x.meta.episode || "Unknown Episode",
      speaker: x.meta.speaker || "Unknown Speaker",
      source: x.meta.source || "Unknown Source",
      quote: x.meta.text
    }));

    res.json({
      answer: quotes.join("\n\n"),
      sources
    });

  } catch (err) {
    res.json({
      answer: "Server error while querying Ask Coach Bryan.",
      error: err.message
    });
  }
});

/* ================== START ================== */
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF] Ask Coach Bryan running on :${SERVER_PORT}`);
});
