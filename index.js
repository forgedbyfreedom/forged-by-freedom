import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

/* =======================
   ENVIRONMENT
======================= */
const {
  OPENROUTER_API_KEY,
  PINECONE_API_KEY,
  PINECONE_HOST,
  PORT
} = process.env;

// Model choice: stability > speed now that prompt is constrained
const MODEL = "nousresearch/hermes-3-llama-3.1-70b";

/* =======================
   RETRIEVAL / PROMPT LIMITS
======================= */
const TOP_K = 4;                 // ↓ from 8
const MAX_CONTEXT_CHARS = 6000;  // total context cap
const PER_SOURCE_LIMIT = 1200;   // per-source quote cap (critical)
const MAX_SOURCES = 3;

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", async (_req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    model: MODEL,
    pineconeQueryUrl: `${PINECONE_HOST}/query`,
    time: new Date().toISOString()
  });
});

/* =======================
   MAIN ASK ENDPOINT
======================= */
app.post("/ask", async (req, res) => {
  try {
    const question = req.body?.question?.trim();
    if (!question) {
      return res.status(400).json({ error: "No question provided" });
    }

    /* ---------- 1) EMBEDD ---------- */
    const embRes = await fetch("https://openrouter.ai/api/v1/embeddings", {
      method: "POST",
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
    const vector = emb?.data?.[0]?.embedding;
    if (!vector) {
      throw new Error("Embedding failed");
    }

    /* ---------- 2) PINECONE QUERY ---------- */
    const pcRes = await fetch(`${PINECONE_HOST}/query`, {
      method: "POST",
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
    const matches = pc?.matches || [];

    if (!matches.length) {
      return res.json({
        answer: "Not enough quoted evidence in the database to answer this question."
      });
    }

    /* ---------- 3) BUILD SAFE, ATTRIBUTED CONTEXT ---------- */
    let used = 0;
    const blocks = [];

    for (let i = 0; i < matches.length && blocks.length < MAX_SOURCES; i++) {
      const md = matches[i]?.metadata || {};

      const rawText =
        md.text ||
        md.chunk ||
        md.content ||
        md.transcript ||
        "";

      if (!rawText) continue;

      const remaining = MAX_CONTEXT_CHARS - used;
      if (remaining <= 0) break;

      // Per-source cap prevents a single transcript chunk from nuking the prompt
      const sliceLen = Math.min(remaining, PER_SOURCE_LIMIT);
      const quote = rawText.slice(0, sliceLen);

      blocks.push(
        `SOURCE ${blocks.length + 1}
Podcast: ${md.podcast || "Unknown Podcast"}
Episode: ${md.episode || md.title || "Unknown Episode"}
Speaker: ${md.speaker || "Unknown Speaker"}

"${quote}"`
      );

      used += quote.length;
    }

    const context = blocks.join("\n\n");

    if (!context.trim()) {
      return res.json({
        answer: "Not enough quoted evidence in the database to answer this question."
      });
    }

    /* ---------- 4) LLM COMPLETION (HARDENED) ---------- */
    const prompt = `
You are Coach Bryan’s AI assistant.

CRITICAL RULES (NO EXCEPTIONS):
- You may ONLY use the quoted database context below.
- You MUST include direct quotes in quotation marks.
- Every quote MUST be attributed with Podcast, Episode, and Speaker.
- Do NOT invent quotes or metadata.
- If the context is insufficient, say:
  "Not enough quoted evidence in the database to answer this question."

RESPONSE FORMAT (REQUIRED):

Answer:
(2–5 sentences derived ONLY from quoted material)

Sources:
- Podcast:
  Episode:
  Speaker:
  Quote: "..."

(Repeat for each source used; use 1–3 sources only.)

Explanation:
- Bullet points explaining WHY the quotes support the answer.
- Derived ONLY from the quoted text.

DATABASE CONTEXT:
${context}

QUESTION:
${question}
`.trim();

    const llmRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        temperature: 0.2,
        max_tokens: 600, // ✅ prevents empty-choice behavior
        messages: [{ role: "user", content: prompt }]
      })
    });

    const llm = await llmRes.json();

    if (!llm?.choices || llm.choices.length === 0) {
      throw new Error("LLM returned empty choices (prompt rejected)");
    }

    const answer = (llm.choices[0]?.message?.content || "").trim();

    if (!answer) {
      return res.json({
        answer: "Not enough quoted evidence in the database to answer this question."
      });
    }

    return res.json({ answer });

  } catch (err) {
    return res.status(500).json({
      error: "AI backend failure",
      details: err.message
    });
  }
});

/* =======================
   START SERVER
======================= */
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF API] running on port ${SERVER_PORT} using ${MODEL}`);
});
