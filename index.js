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

/* Prevent https://https:// forever */
const PINECONE_HOST = RAW_PINECONE_HOST
  .trim()
  .replace(/^https?:\/\//, "")
  .replace(/\/$/, "");

const PINECONE_QUERY_URL = `https://${PINECONE_HOST}/query`;

/* =======================
   PERFORMANCE TUNING
======================= */
// ✅ FAST MODEL to stay under Wix timeouts
const MODEL = "nousresearch/hermes-3-llama-3.1-8b";

// ✅ Reduce work
const TOP_K = 4;                 // fewer matches
const MAX_SOURCES_USED = 3;       // only show 1–3 sources
const MAX_CHARS_PER_QUOTE = 700;  // shorter context => faster LLM

// ✅ Hard time budgets
const EMBED_TIMEOUT_MS = 3500;
const PINECONE_TIMEOUT_MS = 3500;
const LLM_TIMEOUT_MS = 4500;

// Total should stay ~ under 10s worst case; typically 2–5s warm

/* =======================
   HELPERS
======================= */
function withTimeout(ms) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), ms);
  return { controller, t };
}

function pickText(md) {
  if (!md) return "";
  return (
    (typeof md.text === "string" && md.text) ||
    (typeof md.chunk === "string" && md.chunk) ||
    (typeof md.content === "string" && md.content) ||
    (typeof md.transcript === "string" && md.transcript) ||
    (typeof md.body === "string" && md.body) ||
    ""
  ).trim();
}

function safeField(md, key, fallback) {
  const v = md && typeof md[key] === "string" ? md[key].trim() : "";
  return v || fallback;
}

function buildSources(matches) {
  const sources = [];

  for (let i = 0; i < matches.length && sources.length < MAX_SOURCES_USED; i++) {
    const md = matches[i]?.metadata || {};
    const text = pickText(md);
    if (!text) continue;

    sources.push({
      podcast: safeField(md, "podcast", "Unknown Podcast"),
      episode: safeField(md, "episode", md.title ? String(md.title) : "Unknown Episode"),
      speaker: safeField(md, "speaker", "Unknown Speaker"),
      quote: text.slice(0, MAX_CHARS_PER_QUOTE)
    });
  }

  return sources;
}

function renderAnswerFallback(question, sources) {
  const lines = [];
  lines.push("Not enough database evidence to produce a fully supported answer with quotes.");
  lines.push("");
  lines.push("Sources:");
  sources.forEach((s) => {
    lines.push(`- Podcast: ${s.podcast}`);
    lines.push(`  Episode: ${s.episode}`);
    lines.push(`  Speaker: ${s.speaker}`);
    lines.push(`  Quote: "${s.quote}"`);
  });
  lines.push("");
  lines.push("Try asking a more specific question (symptom, dosage range, timing, or mechanism).");
  return lines.join("\n");
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

    /* ---------- 1) EMBEDD ---------- */
    let vector;
    const { controller: embCtl, t: embT } = withTimeout(EMBED_TIMEOUT_MS);
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
    let matches = [];
    const { controller: pcCtl, t: pcT } = withTimeout(PINECONE_TIMEOUT_MS);
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

    // ✅ Short-circuit if Pinecone returns nothing usable
    const sources = buildSources(matches);
    if (sources.length < 1) {
      return res.json({
        answer:
          "No relevant quoted material found in the Forged by Freedom database for this question. Ask more specifically or ingest more transcripts with metadata (podcast/episode/speaker)."
      });
    }

    const context = sources
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

    /* ---------- 3) LLM ---------- */
    const { controller: llmCtl, t: llmT } = withTimeout(LLM_TIMEOUT_MS);

    const prompt = `
You are Coach Bryan’s AI assistant.

MANDATORY RULES:
- Use ONLY the database context below.
- You MUST include 1–3 sources (depending on what is provided).
- For EACH source, include Podcast, Episode, Speaker, and at least one VERBATIM QUOTE from the context.
- NEVER fabricate quotes or source fields.
- If the database context is insufficient to support a claim, write: "Not enough quoted evidence in the database."

OUTPUT FORMAT (required):
Answer (2–6 sentences)

Sources:
- Podcast:
  Episode:
  Speaker:
  Quote: "..."

Explanation (bullets, derived ONLY from the quoted sources)

DATABASE CONTEXT:
${context}

QUESTION:
${question}
`.trim();

    let answerText = "";
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

    // ✅ Never return empty; fallback includes exact quotes + attribution
    if (!answerText) {
      return res.json({ answer: renderAnswerFallback(question, sources) });
    }

    return res.json({ answer: answerText });

  } catch (err) {
    const msg =
      err?.name === "AbortError"
        ? "AI request exceeded time budget. Try a more specific question."
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
