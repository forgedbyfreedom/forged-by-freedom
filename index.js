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

const MODEL = "nousresearch/hermes-3-llama-3.1-8b";
const MAX_QUOTES = 3;
const MAX_QUOTE_CHARS = 700;
const TOP_K = 4;

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", async (req, res) => {
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

    /* ---------- EMBEDDING ---------- */
    const embRes = await fetch("https://openrouter.ai/api/v1/embeddings", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
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

    /* ---------- PINECONE QUERY ---------- */
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
    const matches = (pc.matches || []).slice(0, MAX_QUOTES);

    if (!matches.length) {
      return res.json({
        answer:
          "Not enough quoted evidence in the database to answer this question."
      });
    }

    /* ---------- CONTEXT BUILDER ---------- */
    const context = matches
      .map((m, i) => {
        const md = m.metadata || {};
        const text =
          md.text ||
          md.chunk ||
          md.content ||
          md.transcript ||
          "";

        return `
SOURCE ${i + 1}
Podcast: ${md.podcast || "Unknown"}
Episode: ${md.episode || "Unknown"}
Speaker: ${md.speaker || "Unknown"}

"${text.slice(0, MAX_QUOTE_CHARS)}"
`.trim();
      })
      .join("\n\n");

    /* ---------- PROMPT (LOCKED FORMAT) ---------- */
    const prompt = `
You are Coach Bryan’s AI assistant.

CRITICAL RULES (NO EXCEPTIONS):
- You may ONLY use the database context provided below.
- You MUST quote directly from the context using quotation marks.
- Every quote MUST be attributed with Podcast, Episode, and Speaker.
- DO NOT summarize or paraphrase quoted material.
- If the context does not clearly support an answer, you MUST say:
  "Not enough quoted evidence in the database to answer this question."

RESPONSE FORMAT (REQUIRED):

Answer:
(2–5 sentences derived ONLY from quoted material)

Sources:
- Podcast: <podcast name>
  Episode: <episode name or number>
  Speaker: <speaker name>
  Quote: "<verbatim quote>"

(Repeat the source block for each source used. Use 1–3 sources only.)

Explanation:
- Bullet points explaining WHY the quotes answer the question.
- Explanations must be derived ONLY from the quoted text.

DATABASE CONTEXT:
${context}

QUESTION:
${question}
`.trim();

    /* ---------- LLM CALL ---------- */
    const llmRes = await fetch(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          temperature: 0.15,
          messages: [{ role: "user", content: prompt }]
        })
      }
    );

    const llm = await llmRes.json();
    const answer = llm?.choices?.[0]?.message?.content;

    if (!answer || !answer.trim()) {
      return res.json({
        answer:
          "Not enough quoted evidence in the database to answer this question."
      });
    }

    res.json({ answer });

  } catch (err) {
    res.status(500).json({
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
