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
  PORT
} = process.env;

const MODEL = "nousresearch/hermes-3-llama-3.1-70b";
const MAX_CONTEXT_CHARS = 1100;
const MIN_SOURCES_REQUIRED = 2;

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", (req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    model: MODEL,
    pineconeQueryUrl: `${PINECONE_HOST}/query`,
    time: new Date().toISOString()
  });
});

/* =======================
   ASK ENDPOINT (OPTION A)
======================= */
app.post("/ask", async (req, res) => {
  try {
    const question = req.body?.question;
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

    /* ---------- PINECONE QUERY ---------- */
    const pcRes = await fetch(`${PINECONE_HOST}/query`, {
      method: "POST",
      headers: {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        vector,
        topK: 12,
        includeMetadata: true
      })
    });

    const pc = await pcRes.json();
    const matches = (pc.matches || []).filter(m => m.metadata?.text);

    if (matches.length < MIN_SOURCES_REQUIRED) {
      return res.json({
        answer:
          "Insufficient quoted material in the database to responsibly answer this question."
      });
    }

    /* ---------- BUILD MULTI-SOURCE CONTEXT ---------- */
    const contextBlocks = matches.slice(0, 6).map((m, i) => {
      const md = m.metadata;
      return `
SOURCE ${i + 1}
Podcast: ${md.podcast || "Unknown"}
Episode: ${md.episode || "Unknown"}
Speaker: ${md.speaker || "Unknown"}

"${md.text.slice(0, MAX_CONTEXT_CHARS)}"
`;
    }).join("\n\n");

    /* ---------- LLM CALL ---------- */
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
              role: "system",
              content:
                "You are an evidence-based expert. You may synthesize conclusions ONLY by explicitly connecting multiple quoted sources. Every factual claim MUST be supported by at least one quote. If quotes are insufficient, say so clearly."
            },
            {
              role: "user",
              content:
                "Use the following sources to answer the question.\n\n" +
                contextBlocks +
                "\n\nQuestion:\n" +
                question
            }
          ]
        })
      }
    );

    const llm = await llmRes.json();
    const answer = llm?.choices?.[0]?.message?.content;

    if (!answer) {
      return res.json({
        answer:
          "Relevant material was found, but the sources do not sufficiently support a clear conclusion."
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
  console.log(`[FBF API] running on port ${SERVER_PORT}`);
});
