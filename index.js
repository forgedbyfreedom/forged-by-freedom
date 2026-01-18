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
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT
} = process.env;

const CHAT_MODEL =
  OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
const EMBED_MODEL = "text-embedding-3-large";

/* =========================
   PINECONE
========================= */
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index("forged-freedom-ai");

/* =========================
   EXPRESS
========================= */
const app = express();
app.use(cors());
app.use(bodyParser.json());

/* =========================
   STATUS
========================= */
app.get("/status", async (_req, res) => {
  const stats = await index.describeIndexStats();
  res.json({
    status: "ok",
    model: CHAT_MODEL,
    embedModel: EMBED_MODEL,
    index: "forged-freedom-ai",
    namespaces: Object.keys(stats.namespaces || {}),
    time: new Date().toISOString()
  });
});

/* =========================
   HELPERS
========================= */
async function embed(text) {
  const r = await fetch("https://openrouter.ai/api/v1/embeddings", {
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

  const j = await r.json();
  if (!j?.data?.[0]?.embedding) {
    throw new Error("Embedding failed");
  }
  return j.data[0].embedding;
}

async function searchPinecone(vector) {
  const r = await index.query({
    vector,
    topK: 40,
    includeMetadata: true
  });
  return r.matches || [];
}

/* =========================
   TERM SCORING (NO FILTERING)
========================= */
function countHits(text, terms) {
  const t = text.toLowerCase();
  let hits = 0;

  for (const term of terms) {
    const re = new RegExp(`\\b${term}\\b`, "i");
    if (re.test(t)) hits++;
  }

  return hits;
}

/* =========================
   ASK (QUOTE-ONLY, UNRESTRICTED)
========================= */
app.post("/ask", async (req, res) => {
  const { question } = req.body;

  if (!question || !question.trim()) {
    return res.json({
      answer: "No question provided.",
      sources: []
    });
  }

  try {
    /* ---- EMBED QUESTION ---- */
    const vector = await embed(question);

    /* ---- VECTOR SEARCH ---- */
    const matches = await searchPinecone(vector);

    if (!matches.length) {
      return res.json({
        answer:
          "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    /* ---- DYNAMIC TERM EXTRACTION ---- */
    const q = question.toLowerCase();

    const entityTerms = [];
    const qualifierTerms = [];

    // Broad entity hints (NOT REQUIRED to match)
    if (q.includes("tren")) entityTerms.push("tren", "trenbolone", "19-nor");
    if (q.includes("eq")) entityTerms.push("eq", "boldenone");
    if (q.includes("test")) entityTerms.push("testosterone");
    if (q.includes("glp")) entityTerms.push("glp", "gip", "retatrutide", "semaglutide");
    if (q.includes("gh")) entityTerms.push("growth hormone", "somatropin");

    // Contextual qualifiers (optional)
    if (q.includes("woman") || q.includes("female"))
      qualifierTerms.push("woman", "women", "female", "viril");

    if (q.includes("lipid") || q.includes("cholesterol"))
      qualifierTerms.push("ldl", "hdl", "apob", "cholesterol");

    /* ---- RE-RANK (NO EXCLUSION) ---- */
    const reranked = matches
      .map(m => {
        const text = m.metadata?.text || "";
        const pineconeScore = m.score || 0;
        const entityHits = countHits(text, entityTerms);
        const qualifierHits = countHits(text, qualifierTerms);

        const finalScore =
          pineconeScore * 0.6 +
          entityHits * 0.25 +
          qualifierHits * 0.15;

        return {
          ...m,
          finalScore
        };
      })
      .sort((a, b) => b.finalScore - a.finalScore);

    const strong = reranked.filter(r => r.finalScore > 0.55);

    if (!strong.length) {
      return res.json({
        answer:
          "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    /* ---- FORMAT QUOTES ---- */
    const quotes = strong.slice(0, 8).map((m, i) => {
      const md = m.metadata || {};
      return {
        number: i + 1,
        podcast: md.podcast || "Unknown Podcast",
        episode: md.episode || "Unknown Episode",
        speaker: md.speaker || "Unknown Speaker",
        quote: md.text || ""
      };
    });

    const answerText = quotes
      .map(
        q =>
          `${q.number}) "${q.quote}" — ${q.speaker}, ${q.podcast}`
      )
      .join("\n\n");

    res.json({
      answer: answerText,
      sources: quotes
    });
  } catch (err) {
    console.error(err);
    res.json({
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
  console.log(
    `[FBF] Ask Coach Bryan running on :${SERVER_PORT} (QUOTE-ONLY, UNRESTRICTED)`
  );
});
