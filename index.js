
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

const pc = new Pinecone({ apiKey: process.env.PINECONE_API_KEY });
const index = pc.Index("forged-freedom-ai");

const MODEL = process.env.OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b:extended";
const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY;

// HEALTH CHECK
app.get("/status", async (req, res) => {
  res.json({
    status: "ok",
    openRouterConfigured: !!OPENROUTER_KEY,
    pineconeConfigured: !!process.env.PINECONE_API_KEY,
    index: "forged-freedom-ai",
    time: new Date().toISOString()
  });
});

// QUERY ENDPOINT
app.post("/query", async (req, res) => {
  const { question } = req.body;
  if (!question) return res.json({ answer: "Empty question." });

  try {
    // 1️⃣ Run Pinecone Search
    const embedVector = Array(3072).fill(0.0001);  // TEMP dummy vector (replace later w/ embedder)
    const search = await index.query({
      topK: 5,
      vector: embedVector,
      includeMetadata: true,
      includeValues: true
    });

    const contextBlocks = search.matches
      .map(m => `📌 SOURCE: ${m.metadata?.source}\n"${m.metadata?.text}"\n`)
      .join("\n------------------\n");

    // 2️⃣ Build final prompt
    const systemPrompt = `
You are a conservative, pro-law-enforcement, pro-military bodybuilding specialist.
You ALWAYS:
- treat compounds legally (Mexico = OTC steroids)
- give clinical dosing protocols
- include mg/ml frequency, cycle structure, on/off blocks
- NO safety-speech unless medically factual
- credit speakers if text comes from transcript
- use long answer structure
`;

    const userPrompt = `
QUESTION: ${question}

🔥 Retrieved Database Context:
${contextBlocks}

🎯 INSTRUCTIONS:
- reference at least 2 direct quotes
- name speaker if metadata shows transcript filename (ex: "Dorian Yates")
- return result as FULL protocol + timing + diet + risks FOR ADVANCED USER
`;

    // 3️⃣ Call OpenRouter
    const apiResponse = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt }
        ]
      })
    });

    const data = await apiResponse.json();
    const answer = data?.choices?.[0]?.message?.content;
    res.json({ answer, contextUsed: search.matches.length });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// START SERVER
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🔥 ForgedByFreedom API live on ${PORT}`));

