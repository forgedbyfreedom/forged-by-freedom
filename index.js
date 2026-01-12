import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

const {
  OPENROUTER_API_KEY,
  PINECONE_API_KEY,
  PINECONE_HOST,
  MODEL = "nousresearch/hermes-3-llama-3.1-8b",
  PORT = 5051
} = process.env;

/* =======================
   HEALTH
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
   ASK
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
    if (!vector) throw new Error("Embedding failed");

    /* ---------- PINECONE ---------- */
    const pcRes = await fetch(`${PINECONE_HOST}/query`, {
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
        answer: "No relevant material found in the database."
      });
    }

    /* ---------- CONTEXT (NAMED SOURCES) ---------- */
    const context = matches.slice(0, 3).map((m, i) => {
      const md = m.metadata || {};
      const quote =
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

"${quote.slice(0, 900)}"
`;
    }).join("\n");

    /* ---------- LLM ---------- */
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
Answer the question using ONLY the sources below.
Name each source explicitly.
Quote directly where relevant.

SOURCES:
${context}

QUESTION:
${question}
`
            }
          ]
        })
      }
    );

    const llm = await llmRes.json();
    const answer = llm?.choices?.[0]?.message?.content;

    if (!answer) {
      throw new Error("LLM returned empty response");
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
   START
======================= */
app.listen(PORT, () => {
  console.log(`[FBF API] running on port ${PORT} using ${MODEL}`);
});
