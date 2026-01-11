import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

/* =======================
   ENV + SANITIZATION
======================= */
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const PINECONE_API_KEY = process.env.PINECONE_API_KEY;
const RAW_PINECONE_HOST = process.env.PINECONE_HOST || "";
const PORT = process.env.PORT || 5051;

if (!OPENROUTER_API_KEY) throw new Error("OPENROUTER_API_KEY not set");
if (!PINECONE_API_KEY) throw new Error("PINECONE_API_KEY not set");
if (!RAW_PINECONE_HOST) throw new Error("PINECONE_HOST not set");

// Prevent https://https:// and trailing slash issues forever.
const PINECONE_HOST = RAW_PINECONE_HOST
  .trim()
  .replace(/^https?:\/\//, "")
  .replace(/\/$/, "");

const PINECONE_QUERY_URL = `https://${PINECONE_HOST}/query`;

/* =======================
   PERFORMANCE TUNING
======================= */
// Use a fast model so Wix never 504s.
// Keep retrieval the source of truth.
const MODEL = "nousresearch/hermes-3-llama-3.1-8b";

// Keep context tight to reduce token/latency.
const TOP_K = 4;              // we only use top 3 anyway
const MAX_CHARS_PER_QUOTE = 900;
const MAX_SOURCES_USED = 3;

// Hard timeouts so Render returns before Wix kills it.
const EMBED_TIMEOUT_MS = 4500;
const PINECONE_TIMEOUT_MS = 4500;
const LLM_TIMEOUT_MS = 6500;

/* =======================
   HELPERS
======================= */
function withTimeout(ms) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), ms);
  return { controller, t };
}

function safeMeta(md, keyCandidates) {
  for (const k of keyCandidates) {
    if (md && typeof md[k] === "string" && md[k].trim()) return md[k].trim();
  }
  return "";
}

function buildSources(matches) {
  const sources = [];

  for (let i = 0; i < matches.length && sources.length < MAX_SOURCES_USED; i++) {
    const md = matches[i]?.metadata || {};

    const podcast = safeMeta(md, ["podcast", "show", "channel"]);
    const episode = safeMeta(md, ["episode", "title", "video_title", "name"]);
    const speaker = safeMeta(md, ["speaker", "author", "host"]);

    const text =
      safeMeta(md, ["text"]) ||
      safeMeta(md, ["chunk"]) ||
      safeMeta(md, ["content"]) ||
      safeMeta(md, ["transcript"]) ||
      safeMeta(md, ["body"]);

    if (!text) continue;

    sources.push({
      podcast: podcast || "Unknown Podcast",
      episode: episode || "Unknown Episode",
      speaker: speaker || "Unknown Speaker",
      quote: text.slice(0, MAX_CHARS_PER_QUOTE)
    });
  }

  return sources;
}

function formatContext(sources) {
  return sources
    .map((s, i) => {
      return [
        `SOURCE ${i + 1}`,
        `Podcast: ${s.podcast}`,
        `Episode: ${s.episode}`,
        `Speaker: ${s.speaker}`,
        ``,
        `VERBATIM QUOTE:`,
        `"${s.quote}"`
      ].join("\n");
    })
    .join("\n\n");
}

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", (_req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    model: MODEL,
    pineconeQueryUrl: PINECONE_QUERY_URL,
    time: new Date().toISOString()
  });
});

/* =======================
   MAIN ASK ENDPOINT
======================= */
app.post("/ask", async (req, res) => {
  try {
    const question = (req.body?.question || "").trim();
    if (!question) return res.status(400).json({ error: "No question provided" });

    /* ---------- 1) EMBED ---------- */
    const { controller: embCtl, t: embT } = withTimeout(EMBED_TIMEOUT_MS);
    let vector;

    try {
      const embRes = await fetch("https://openrouter.ai/api/v1/embeddings", {
        method: "POST",
        signal: embCtl.signal,
        headers: {
          Authorization: `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: "text-embedding-3-large",
          input: question
        })
      });

      const emb = await embRes.json();
      vector = emb?.data?.[0]?.embedding;
      if (!vector) throw new Error("Embedding failed");
    } finally {
      clearTimeout(embT);
    }

    /* ---------- 2) PINECONE ---------- */
    const { controller: pcCtl, t: pcT } = withTimeout(PINECONE_TIMEOUT_MS);
    let matches = [];

    try {
      const pcRes = await fetch(PINECONE_QUERY_URL, {
        method: "POST",
        signal: pcCtl.signal,
        headers: {
          "Api-Key": PINECONE_API_KEY,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          vector,
          topK: TOP_K,
          includeMetadata: true
        })
      });

      const pc = await pcRes.json();
      matches = pc?.matches || [];
    } finally {
      clearTimeout(pcT);
    }

    const sources = buildSources(matches);

    if (sources.length < 1) {
      return res.json({
        answer:
          "The database did not return usable, attributable source text for this question. Please ask a more specific question or ingest more transcripts with metadata (podcast/episode/speaker)."
      });
    }

    const context = formatContext(sources);

    /* ---------- 3) LLM ---------- */
    const { controller: llmCtl, t: llmT } = withTimeout(LLM_TIMEOUT_MS);
    let answerText = "";

    const prompt = `
You are Coach Bryan’s AI assistant.

MANDATORY RULES:
- Use ONLY the database context below.
- Provide EXACTLY THREE source blocks if possible (if fewer are available, use what is available).
- For each source block, include:
  Podcast, Episode, Speaker, and at least one VERBATIM QUOTE.
- Do NOT invent quotes or metadata.
- If a direct verbatim quote is insufficient for a claim, state: "Not enough quoted evidence in the database."
- After source blocks, write a short explanation derived from the quotes only.

OUTPUT FORMAT (required):
1) Answer (2–6 sentences)
2) Sources (list 1–3 items):
   - Podcast:
   - Episode:
   - Speaker:
   - Quote: "..."
3) Explanation (bullet points)

DATABASE CONTEXT:
${context}

QUESTION:
${question}
`.trim();

    try {
      const llmRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        signal: llmCtl.signal,
        headers: {
          Authorization: `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          temperature: 0.15,
          messages: [{ role: "user", content: prompt }]
        })
      });

      const llm = await llmRes.json();
      answerText = (llm?.choices?.[0]?.message?.content || "").trim();
    } finally {
      clearTimeout(llmT);
    }

    if (!answerText) {
      // Never return empty; return the structured sources as fallback
      const fallback = [
        "Not enough quoted evidence in the database to generate a complete answer.",
        "",
        "Sources:",
        ...sources.map((s, i) => {
          return [
            `- Podcast: ${s.podcast}`,
            `  Episode: ${s.episode}`,
            `  Speaker: ${s.speaker}`,
            `  Quote: "${s.quote}"`
          ].join("\n");
        })
      ].join("\n");
      return res.json({ answer: fallback });
    }

    return res.json({ answer: answerText });

  } catch (err) {
    // If we got aborted by timeout, still respond quickly so Wix doesn’t 504.
    const msg = err?.name === "AbortError"
      ? "AI request exceeded time budget. Please try again with a more specific question."
      : (err?.message || "Unknown error");

    return res.status(500).json({
      error: "AI backend failure",
      details: msg
    });
  }
});

/* =======================
   START SERVER
======================= */
app.listen(PORT, () => {
  console.log(`[FBF API] running on port ${PORT} using ${MODEL}`);
});

