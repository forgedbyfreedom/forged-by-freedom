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
    topK: 30,
    includeMetadata: true
  });
  return r.matches || [];
}

function extractText(md = {}) {
  return (
    md.text ||
    md.chunk ||
    md.content ||
    md.transcript ||
    md.body ||
    ""
  );
}

/* =========================
   ASK (QUOTE-ONLY, UNRESTRICTED)
========================= */
app.post("/ask", async (req, res) => {
  const { question } = req.body;

  if (!question) {
    return res.json({
      answer: "No question provided.",
      sources: []
    });
  }

  try {
    const vector = await embed(question);
    const matches = await searchPinecone(vector);

    if (!matches.length) {
      return res.json({
        answer:
          "Insufficient quoted evidence in the database to answer this question directly.",
        sources: []
      });
    }

    const quotes = matches
      .map(m => {
        const md = m.metadata || {};
        const text = extractText(md).trim();
        if (!text) return null;

        return {
          channel: md.channel || "unknown",
          source: md.source || "unknown",
          text
        };
      })
      .filter(Boolean)
      .slice(0, 8);

    if (!quotes.length) {
      return res.json({
        answer:
          "Relevant sources were found, but no usable transcript text was available.",
        sources: []
      });
    }

    const answerText = quotes
      .map(
        (q, i) =>
          `${i + 1}) "${q.text}" — ${q.channel}`
      )
      .join("\n\n");

    res.json({
      answer: answerText,
      sources: quotes
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
  console.log(
    `[FBF] Ask Coach Bryan running on :${SERVER_PORT} (UNRESTRICTED QUOTE MODE)`
  );
});
