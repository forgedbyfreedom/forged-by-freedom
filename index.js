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

const CHAT_MODEL = OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
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
  if (!j?.data?.[0]?.embedding) throw new Error("Embedding failed");
  return j.data[0].embedding;
}

async function pineconeSearch(vector) {
  const r = await index.query({
    vector,
    topK: 20,
    includeMetadata: true
  });
  return r.matches || [];
}

function containsAny(text, terms) {
  const t = text.toLowerCase();
  return terms.some(k => t.includes(k));
}

/* =========================
   ASK
========================= */
app.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) {
    return res.json({ answer: "No question provided.", sources: [] });
  }

  const q = question.toLowerCase();

  const requiresTren = q.includes("tren");
  const requiresWomen =
    q.includes("woman") || q.includes("women") || q.includes("female");

  try {
    /* ---- 1. Embed ---- */
    const vector = await embed(question);

    /* ---- 2. Retrieve ---- */
    const matches = await pineconeSearch(vector);

    if (!matches.length) {
      return res.json({
        answer: "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    /* ---- 3. HARD RELEVANCE FILTER ---- */
    const filtered = matches.filter(m => {
      const text = (m.metadata?.text || "").toLowerCase();

      if (requiresTren && !containsAny(text, ["tren", "trenbolone", "19-nor"])) {
        return false;
      }

      if (
        requiresWomen &&
        !containsAny(text, ["woman", "women", "female", "viril"])
      ) {
        return false;
      }

      return true;
    });

    if (!filtered.length) {
      return res.json({
        answer:
          "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    /* ---- 4. Context ---- */
    const context = filtered
      .slice(0, 6)
      .map((m, i) => {
        const md = m.metadata || {};
        return `[${i + 1}]
Podcast: ${md.podcast || "Unknown Podcast"}
Episode: ${md.episode || "Unknown Episode"}
Speaker: ${md.speaker || "Unknown Speaker"}
Quote: "${md.text || ""}"`;
      })
      .join("\n\n");

    /* ---- 5. LLM ---- */
    const llm = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://www.forgedbyfreedom.org",
        "X-Title": "Ask Coach Bryan"
      },
      body: JSON.stringify({
        model: CHAT_MODEL,
        messages: [
          {
            role: "system",
            content:
              "Answer ONLY using the provided transcript excerpts. Do not speculate."
          },
          {
            role: "user",
            content: `QUESTION:\n${question}\n\nTRANSCRIPTS:\n${context}`
          }
        ]
      })
    });

    const j = await llm.json();
    const answer = j?.choices?.[0]?.message?.content;

    res.json({
      answer: answer || "No answer generated.",
      sources: filtered.map(m => m.metadata || {})
    });
  } catch (err) {
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
  console.log(`[FBF] Ask Coach Bryan running on :${SERVER_PORT}`);
});
