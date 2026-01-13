import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

// =======================
// ENVIRONMENT VARIABLES
// =======================
const {
  OPENROUTER_API_KEY,
  PINECONE_API_KEY,
  PINECONE_HOST,
  PORT
} = process.env;

// =======================
// MODEL (STABLE)
// =======================
const MODEL = "nousresearch/hermes-3-llama-3.1-8b";

// =======================
// HEALTH CHECK
// =======================
app.get("/status", async (req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    model: MODEL,
    pineconeQueryUrl: `${PINECONE_HOST}/query`,
    time: new Date().toISOString()
  });
});

// =======================
// MAIN ASK ENDPOINT
// =======================
app.post("/ask", async (req, res) => {
  try {
    const question = req.body?.question;
    if (!question) {
      return res.status(400).json({ error: "No question provided" });
    }

    // =======================
    // 1️⃣ EMBEDDING
    // =======================
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

    // =======================
    // 2️⃣ PINECONE QUERY
    // =======================
    const pcRes = await fetch(`${PINECONE_HOST}/query`, {
      method: "POST",
      headers: {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        vector,
        topK: 8,
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

    // =======================
    // 3️⃣ BUILD SAFE CONTEXT
    // =======================
    const MAX_CONTEXT_CHARS = 6000;
    let used = 0;
    const contextBlocks = [];

    for (let i = 0; i < matches.length; i++) {
      const md = matches[i].metadata || {};
      const text =
        md.text ||
        md.chunk ||
        md.content ||
        md.transcript ||
        "";

      if (!text) continue;

      const remaining = MAX_CONTEXT_CHARS - used;
      if (remaining <= 0) break;

      const slice = text.slice(0, remaining);

      contextBlocks.push(
        `SOURCE ${contextBlocks.length + 1}
Podcast: ${md.podcast || "Unknown Podcast"}
Episode: ${md.episode || "Unknown Episode"}
Speaker: ${md.speaker || "Unknown Speaker"}

"${slice}"`
      );

      used += slice.length;
    }

    const context = contextBlocks.join("\n\n");

    // =======================
    // 4️⃣ LLM CALL
    // =======================
    const llmRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        temperature: 0.2,
        messages: [
          {
            role: "system",
            content:
              "You are a bodybuilding and performance research assistant. " +
              "Answer ONLY using the quoted sources provided. " +
              "Cite claims directly with quotes."
          },
          {
            role: "user",
            content:
              `Context:\n${context}\n\nQuestion:\n${question}`
          }
        ]
      })
    });

    const llm = await llmRes.json();

    if (!llm?.choices || llm.choices.length === 0) {
      throw new Error("LLM returned empty choices (prompt too large or rejected)");
    }

    const answer = llm.choices[0].message.content;
    res.json({ answer });

  } catch (err) {
    res.status(500).json({
      error: "AI backend failure",
      details: err.message
    });
  }
});

// =======================
// START SERVER
// =======================
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF API] running on port ${SERVER_PORT} using ${MODEL}`);
});
