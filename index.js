import express from "express";
import cors from "cors";
import fetch from "node-fetch";

/* ===============================
   ENV
================================ */

const {
  OPENROUTER_API_KEY,
  PINECONE_API_KEY,
  PINECONE_HOST,
  PORT
} = process.env;

const MODEL = "nousresearch/hermes-3-llama-3.1-70b";

/* ===============================
   APP
================================ */

const app = express();
app.use(cors());
app.use(express.json());

/* ===============================
   HEALTH CHECK
================================ */

app.get("/status", async (_req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    openRouterConfigured: !!OPENROUTER_API_KEY,
    pineconeConfigured: !!PINECONE_API_KEY,
    model: MODEL,
    time: new Date().toISOString()
  });
});

/* ===============================
   ASK (MAIN ENDPOINT)
================================ */

app.post("/ask", async (req, res) => {
  try {
    const question = req.body?.question;
    if (!question) {
      return res.status(400).json({ error: "No question provided" });
    }

    // 1️⃣ Embed
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

    const embJson = await embRes.json();
    const vector = embJson?.data?.[0]?.embedding;
    if (!vector) throw new Error("Embedding failed");

    // 2️⃣ Pinecone
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

    const pcJson = await pcRes.json();
    const matches = pcJson?.matches || [];

    if (!matches.length) {
      return res.json({
        answer:
          "No relevant material was found in the Forged by Freedom database."
      });
    }

    const context = matches
      .slice(0, 3)
      .map((m, i) => {
        const md = m.metadata || {};
        const text =
          md.text ||
          md.chunk ||
          md.content ||
          md.transcript ||
          md.body ||
          "";
        return `SOURCE ${i + 1}\n${text.slice(0, 1200)}`;
      })
      .join("\n\n");

    // 3️⃣ LLM
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
              content:
                "Use ONLY the context below.\n\n" +
                context +
                "\n\nQuestion:\n" +
                question
            }
          ]
        })
      }
    );

    const llmJson = await llmRes.json();
    const answer = llmJson?.choices?.[0]?.message?.content;
    if (!answer) throw new Error("LLM returned no answer");

    res.json({ answer });

  } catch (err) {
    console.error("[ASK ERROR]", err);
    res.status(500).json({
      error: "AI backend failure",
      details: err.message
    });
  }
});

/* ===============================
   START
================================ */

const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(
    `[FBF API] running on port ${SERVER_PORT} using ${MODEL}`
  );
});

