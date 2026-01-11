import express from "express";
import cors from "cors";
import fetch from "node-fetch";

/* =======================
   APP SETUP
======================= */
const app = express();
app.use(cors());
app.use(express.json());

/* =======================
   ENV VARS (SANITIZED)
======================= */
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const PINECONE_API_KEY   = process.env.PINECONE_API_KEY;
const RAW_PINECONE_HOST  = process.env.PINECONE_HOST || "";
const PORT               = process.env.PORT || 5051;

if (!OPENROUTER_API_KEY) throw new Error("OPENROUTER_API_KEY not set");
if (!PINECONE_API_KEY)   throw new Error("PINECONE_API_KEY not set");
if (!RAW_PINECONE_HOST)  throw new Error("PINECONE_HOST not set");

/* 🔒 HARD SANITIZATION (prevents double protocol forever) */
const PINECONE_HOST = RAW_PINECONE_HOST
  .trim()
  .replace(/^https?:\/\//, "")
  .replace(/\/$/, "");

const PINECONE_QUERY_URL = `https://${PINECONE_HOST}/query`;

/* =======================
   MODEL CONFIG
======================= */
const MODEL = "nousresearch/hermes-3-llama-3.1-8b"; // Wix-safe latency

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", async (req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    openRouterConfigured: true,
    pineconeConfigured: true,
    pineconeQueryUrl: PINECONE_QUERY_URL,
    model: MODEL,
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

    /* ---------- 1️⃣ EMBEDDING ---------- */
    const embRes = await fetch(
      "https://openrouter.ai/api/v1/embeddings",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: "text-embedding-3-large",
          input: question
        })
      }
    );

    const emb = await embRes.json();
    const vector = emb?.data?.[0]?.embedding;
    if (!vector) throw new Error("Embedding failed");

    /* ---------- 2️⃣ PINECONE QUERY ---------- */
    console.log("FINAL PINECONE QUERY URL:", PINECONE_QUERY_URL);

    const pcRes = await fetch(PINECONE_QUERY_URL, {
      method: "POST",
      headers: {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        vector,
        topK: 6,
        includeMetadata: true
      })
    });

    const pc = await pcRes.json();
    const matches = pc?.matches || [];

    if (!matches.length) {
      return res.json({
        answer:
          "The Forged by Freedom database does not contain sufficient cited material to answer this question."
      });
    }

    /* ---------- 3️⃣ CONTEXT (HARD-STRUCTURED SOURCES) ---------- */
    const context = matches
      .slice(0, 3)
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
Podcast: ${md.podcast || "Unknown Podcast"}
Episode: ${md.episode || md.title || "Unknown Episode"}
Speaker: ${md.speaker || "Unknown Speaker"}

VERBATIM QUOTE:
"${text.slice(0, 1200)}"
`;
      })
      .join("\n\n");

    /* ---------- 4️⃣ LLM COMPLETION (STRICT) ---------- */
    const llmRes = await fetch(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          temperature: 0.2,
          messages: [
            {
              role: "user",
              content: `
You are Coach Bryan’s AI assistant.

STRICT RULES (MANDATORY):
1. You MUST answer using ONLY the database context below.
2. You MUST include at least THREE direct quotes.
3. Each quote MUST list:
   - Podcast name
   - Episode
   - Speaker
4. Quotes MUST be verbatim.
5. After the quotes, explain the physiological or medical reasoning.
6. Do NOT introduce outside knowledge.
7. If proper citations are not possible, state that clearly.
8. Answers without named sources are INVALID.

DATABASE CONTEXT:
${context}

USER QUESTION:
${question}
`
            }
          ]
        })
      }
    );

    const llm = await llmRes.json();
    const answer = llm?.choices?.[0]?.message?.content;

    if (!answer) throw new Error("LLM returned empty response");

    return res.json({ answer });

  } catch (err) {
    console.error("AI backend error:", err);
    return res.status(500).json({
      error: "AI backend failure",
      details: err.message
    });
  }
});

/* =======================
   START SERVER
======================= */
app.listen(PORT, () => {
  console.log(`[FBF API] running on port ${PORT} using ${MODEL}`);
});
