import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

/* =========================
   ENV
========================= */
const {
  OPENROUTER_API_KEY,
  PINECONE_API_KEY,
  PORT
} = process.env;

if (!OPENROUTER_API_KEY || !PINECONE_API_KEY) {
  console.error("❌ Missing OPENROUTER_API_KEY or PINECONE_API_KEY");
  process.exit(1);
}

const INDEX_NAME = "forged-freedom-ai";
const EMBED_MODEL = "openai/text-embedding-3-large";

/* =========================
   PINECONE
========================= */
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index(INDEX_NAME);

/* =========================
   EXPRESS
========================= */
const app = express();
app.use(cors());
app.use(bodyParser.json());

/* =========================
   HEALTH
========================= */
app.get("/status", async (req, res) => {
  try {
    const stats = await index.describeIndexStats();
    res.json({
      status: "ok",
      index: INDEX_NAME,
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

/* =========================
   HELPERS
========================= */
const normalize = (t = "") => t.toLowerCase();

const containsAllAnchors = (text, anchors) => {
  const t = normalize(text);
  return anchors.every(a => t.includes(a));
};

/* =========================
   ASK COACH BRYAN
========================= */
app.post("/ask", async (req, res) => {
  const { question } = req.body;

  if (!question) {
    return res.json({ answer: "No question provided.", sources: [] });
  }

  try {
    /* ---------- 1. EMBED QUERY ---------- */
    const embedResp = await fetch("https://openrouter.ai/api/v1/embeddings", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "HTTP-Referer": "https://www.forgedbyfreedom.org",
        "X-Title": "Ask Coach Bryan",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: EMBED_MODEL,
        input: question
      })
    });

    const embedData = await embedResp.json();

    if (!embedData?.data?.length) {
      return res.json({
        answer: "Embedding failed — no vector returned.",
        debug: embedData
      });
    }

    const queryVector = embedData.data[0].embedding;

    /* ---------- 2. BUILD REQUIRED RELEVANCE ANCHORS ---------- */
    const q = normalize(question);
    const requiredAnchors = [];

    if (q.includes("tren")) requiredAnchors.push("tren");

    if (q.includes("woman") || q.includes("women") || q.includes("female")) {
      requiredAnchors.push("women");
    }

    if (
      q.includes("viril") ||
      q.includes("mascul") ||
      q.includes("androgen") ||
      q.includes("voice") ||
      q.includes("clitor")
    ) {
      requiredAnchors.push("viril");
    }

    /* ---------- 3. QUERY MULTIPLE NAMESPACES ---------- */
    const namespaces = [
      "",
      "default",
      "transcripts",
      "thinkbig_priority",
      "anabolic_bodybuilding_priority",
      "women_steroids"
    ];

    let allMatches = [];

    for (const ns of namespaces) {
      const result = await index.query({
        vector: queryVector,
        topK: 15,
        includeMetadata: true,
        namespace: ns || undefined
      });

      if (result?.matches?.length) {
        allMatches.push(...result.matches);
      }
    }

    /* ---------- 4. HARD FILTER BY RELEVANCE ---------- */
    const relevant = allMatches.filter(m => {
      const text = m.metadata?.text || "";
      return containsAllAnchors(text, requiredAnchors);
    });

    if (!relevant.length) {
      return res.json({
        answer:
          "No verbatim transcript quotes directly addressing this question were found.",
        sources: []
      });
    }

    /* ---------- 5. DEDUPE + SELECT TOP QUOTES ---------- */
    const seen = new Set();
    const selected = [];

    for (const m of relevant) {
      const text = m.metadata.text;
      if (!seen.has(text)) {
        seen.add(text);
        selected.push(m);
      }
      if (selected.length === 3) break;
    }

    /* ---------- 6. FORMAT RESPONSE ---------- */
    const formatted = selected.map((m, i) => ({
      id: i + 1,
      quote: m.metadata.text,
      speaker: m.metadata.speaker || "Unknown Speaker",
      podcast: m.metadata.podcast || "Unknown Podcast",
      source: m.metadata.source || "Transcript"
    }));

    res.json({
      answer: formatted
        .map(
          q =>
            `${q.id}) "${q.quote}" — ${q.speaker}, ${q.podcast}`
        )
        .join("\n\n"),
      sources: formatted
    });

  } catch (err) {
    res.status(500).json({
      answer: "Server error while querying Ask Coach Bryan.",
      error: err.message
    });
  }
});

/* =========================
   START
========================= */
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF] Ask Coach Bryan running on :${SERVER_PORT}`);
});
