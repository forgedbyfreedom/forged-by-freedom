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

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", (req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    openRouterConfigured: !!OPENROUTER_API_KEY,
    pineconeConfigured: !!PINECONE_API_KEY,
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
    const matches = pc.matches || [];

    if (!matches.length) {
      return res.json({
        answer:
          "No relevant material was found in the Forged by Freedom knowledge base."
      });
    }

    /* ---------- CONTEXT ---------- */
    const context = matches.slice(0, 4).map((m, i) => {
      const md = m.metadata || {};
      return `
SOURCE ${i + 1}
Podcast: ${md.podcast || "Unknown"}
Episode: ${md.episode || "Unknown"}
Speaker: ${md.speaker || "Unknown"}

${(md.text || md.chunk || "").slice(0, 1400)}
      `.trim();
    }).join("\n\n");

    /* ---------- LLM ---------- */
    const prompt = `
You are Coach Bryan’s AI assistant.

RULES (follow exactly):
- Use ONLY the provided sources.
- If a direct quote exists, include it in quotation marks.
- If no exact quote exists, paraphrase and clearly label it as a paraphrase.
- Always list sources with podcast name, episode, and speaker.
- NEVER fabricate quotes.
- If evidence is insufficient, say so explicitly.

FORMAT:
Answer first.
Then a section titled "Sources" listing each source.

DATABASE CONTEXT:
${context}

QUESTION:
${question}
`.trim();

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
          messages: [{ role: "user", content: prompt }]
        })
      }
    );

    const llm = await llmRes.json();
    const answer = llm?.choices?.[0]?.message?.content?.trim();

    if (!answer) {
      return res.json({
        answer:
          "The database does not contain sufficient quoted material to answer this question with proper attribution."
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
