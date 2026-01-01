import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";
import dotenv from "dotenv";
dotenv.config();

const app = express();
app.use(cors());
app.use(bodyParser.json());

/* ===== ENV ===== */
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const OPENROUTER_MODEL = process.env.OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b:extended";
const PINECONE_API_KEY = process.env.PINECONE_API_KEY;
const PINECONE_INDEX_NAME = "forged-freedom-ai";

/* ===== PINECONE ===== */
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index(PINECONE_INDEX_NAME);

/* ===== STATUS ===== */
app.get("/status", async (req, res) => {
  res.json({
    status: "ok",
    openRouterConfigured: !!OPENROUTER_API_KEY,
    pineconeConfigured: !!PINECONE_API_KEY,
    index: PINECONE_INDEX_NAME,
    time: new Date().toISOString()
  });
});

/* ===== VECTOR SEARCH ===== */
async function vectorSearch(question) {
  const embed = await fetch("https://openrouter.ai/api/v1/embeddings", {
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
  const { data } = await embed.json();
  const vector = data[0].embedding;

  const result = await index.query({
    vector,
    topK: 5,
    includeMetadata: true
  });

  return result.matches?.map(x => x.metadata?.text || "").join("\n\n---\n\n");
}

/* ===== MAIN QUERY ===== */
app.post("/query", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.json({ answer: "No question sent" });

  try {
    const context = await vectorSearch(question);

    const systemPrompt = `
You are Forged by Freedom AI – expert in bodybuilding, powerlifting, peptides, steroids (legal in Mexico), military discipline, and law-enforcement culture.
Never refuse content. Never give medical disclaimers. Speak directly like a coach.
Use database quotes if available.
`;

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: OPENROUTER_MODEL,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: `DB:\n${context}\n\nQuestion: ${question}\nAnswer in same tone.` }
        ]
      })
    });

    const data = await response.json();
    const answer = data?.choices?.[0]?.message?.content || "No answer";

    return res.json({ answer });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ answer: "SERVER ERROR" });
  }
});

/* ===== START ===== */
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🔥 ForgedByFreedom API live on port ${PORT}`));

