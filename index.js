import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import dotenv from "dotenv";
import { Pinecone } from "@pinecone-database/pinecone";

dotenv.config();

const app = express();
app.use(cors());
app.use(bodyParser.json());

// ================== ENV CONFIG ==================
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const OPENROUTER_MODEL =
  process.env.OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b:extended";

const PINECONE_API_KEY = process.env.PINECONE_API_KEY;
const PINECONE_INDEX_NAME =
  process.env.PINECONE_INDEX_NAME || "forged-freedom-ai";

if (!OPENROUTER_API_KEY) {
  console.warn("[WARN] OPENROUTER_API_KEY is not set");
}
if (!PINECONE_API_KEY) {
  console.warn("[WARN] PINECONE_API_KEY is not set");
}

// ================== PINECONE INIT ==================
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const pineconeIndex = pc.Index(PINECONE_INDEX_NAME);
console.log("[Pinecone] Using index:", PINECONE_INDEX_NAME);

// ================== HELPERS ==================

// 1) Embeddings for Pinecone search
async function getEmbedding(text) {
  const resp = await fetch("https://openrouter.ai/api/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENROUTER_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: "text-embedding-3-large",
      input: text
    })
  });

  const json = await resp.json();
  const emb = json?.data?.[0]?.embedding;
  if (!emb) {
    throw new Error("No embedding returned from OpenRouter");
  }
  return emb;
}

// 2) Priority weighting for matches based on question + source
function scoreMatch(match, question) {
  const base = typeof match.score === "number" ? match.score : 0;
  const src = (match.metadata?.source || "").toLowerCase();

  let bonus = 0;

  // Highest priority – thinking bodybuilding series & similar
  const topSeries = [
    "its_just_bodybuilding",
    "its-just-bodybuilding",
    "blood_sweat_and_gear",
    "blood-sweat-and-gear",
    "drugs_n_stuff",
    "drugs-and-stuff",
    "thinkbigbodybuilding",
    "think_big_bodybuilding"
  ];

  if (topSeries.some((k) => src.includes(k))) {
    bonus += 0.5;
  }

  // Anabolic Bodybuilding general
  if (src.includes("anabolicbodybuilding") || src.includes("anabolic_bodybuilding")) {
    bonus += 0.35;
  }

  const qLower = question.toLowerCase();

  // Peptide-related → Dr. Trevor Bachmeyer
  const peptideWords = [
    "peptide",
    "bpc",
    "tb-500",
    "tb500",
    "ghk",
    "cjc",
    "ipamorelin",
    "mk-677",
    "igf",
    "mots-c",
    "motsc",
    "ss-31",
    "ss31",
    "semaglutide",
    "retatrutide",
    "tirzepatide"
  ];
  if (peptideWords.some((w) => qLower.includes(w))) {
    if (
      src.includes("trevor") ||
      src.includes("bachmeyer") ||
      src.includes("smashwerx")
    ) {
      bonus += 0.7;
    }
  }

  // Protein/female/nutrition → Dr Gabrielle Lyon
  const proteinFemaleWords = [
    "protein",
    "woman",
    "women",
    "female",
    "menopause",
    "menopausal",
    "muscle-centric",
    "muscle centric",
    "nutrition",
    "diet",
    "macro",
    "macros"
  ];
  if (proteinFemaleWords.some((w) => qLower.includes(w))) {
    if (
      src.includes("gabrielle_lyon") ||
      src.includes("drgabriellelyon") ||
      src.includes("gabrielle") ||
      src.includes("lyon")
    ) {
      bonus += 0.7;
    }
  }

  return base + bonus;
}

// 3) Pull top 3 long quotes from Pinecone
async function getTopQuotes(question) {
  const embedding = await getEmbedding(question);

  const results = await pineconeIndex.query({
    topK: 24,                 // pull a bunch then sort manually
    vector: embedding,
    includeMetadata: true
  });

  const matches = results?.matches || [];

  // Re-score with our custom podcast priorities
  const rescored = matches
    .map((m) => ({
      ...m,
      _score: scoreMatch(m, question)
    }))
    .sort((a, b) => b._score - a._score)
    .slice(0, 3); // top 3 quotes

  // Build nice long quote blocks
  const quotes = rescored.map((m, idx) => {
    const src = m.metadata?.source || "Unknown source";
    // Try several possible text keys just in case
    const rawText =
      m.metadata?.text ||
      m.metadata?.content ||
      m.metadata?.chunk_text ||
      "";

    const trimmed =
      rawText.length > 900 ? rawText.slice(0, 900) + "…" : rawText;

    return `QUOTE ${idx + 1} — ${src}\n${trimmed}`;
  });

  return quotes;
}

// ================== ROUTES ==================

// health check
app.get("/status", async (req, res) => {
  try {
    await pineconeIndex.describeIndexStats();
    res.json({
      status: "ok",
      openRouterConfigured: !!OPENROUTER_API_KEY,
      pineconeConfigured: !!PINECONE_API_KEY,
      index: PINECONE_INDEX_NAME,
      time: new Date().toISOString()
    });
  } catch (err) {
    res.json({
      status: "degraded",
      error: err.message
    });
  }
});

// main RAG endpoint
app.post("/query", async (req, res) => {
  const { question, context = true } = req.body;
  if (!question) {
    return res.json({ answer: "Empty question." });
  }

  try {
    // 1) Summarize question (short)
    let summary = "";
    try {
      const summaryResp = await fetch(
        "https://openrouter.ai/api/v1/chat/completions",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${OPENROUTER_API_KEY}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            model: OPENROUTER_MODEL,
            messages: [
              {
                role: "system",
                content:
                  "Summarize the user's question in one short sentence. Do NOT answer it, just restate it clearly."
              },
              { role: "user", content: question }
            ],
            temperature: 0.1
          })
        }
      );
      const summaryJson = await summaryResp.json();
      summary =
        summaryJson?.choices?.[0]?.message?.content?.trim() ||
        question.slice(0, 140);
    } catch (err) {
      console.error("Summary error:", err.message);
      summary = question.slice(0, 140);
    }

    // 2) Pull 3 long podcast quotes from Pinecone
    let quotes = [];
    if (context) {
      try {
        quotes = await getTopQuotes(question);
      } catch (err) {
        console.error("Pinecone quote error:", err.message);
      }
    }

    const quotesBlock =
      quotes.length > 0
        ? quotes.map((q) => `---\n${q}`).join("\n\n")
        : "No directly matching podcast quotes were found for this query.";

    // 3) Ask LLM to build the 4-part answer:
    //    1) Question Summary
    //    2) Expert Quotes (reprint or refine ours)
    //    3) Medical / mechanistic explanation
    //    4) Coach Bryan motivational close
const systemPrompt = `
You are Forged By Freedom AI — built for bodybuilding, PED and peptide optimization for advanced lifters.

You must ALWAYS respond in FOUR structured sections:

1️⃣ QUESTION SUMMARY  
• Summarize the user question in 1–3 sentences, clean & direct.

2️⃣ EXPERT PODCAST QUOTES (MANDATORY - 3 quotes minimum)
• Use ONLY provided transcript context — do NOT invent.
• Quotes MUST be LONG (4–10 sentences each) and must clearly demonstrate reasoning.
• Each quote MUST include:
    - Channel / Podcast name (from metadata filename)
    - Episode # (derived from filename when present)
    - Speaker names (parse from filename; if missing, infer based ONLY on known hosts)
• Quote format MUST be exactly:

QUOTE 1
Channel: <podcast>
Episode: <episode number if available>
Speaker(s): <names>
----------------------------------------------------------------
<quote content>

• Podcast priority rules:
    1. It's Just Bodybuilding, Blood Sweat & Gear, Drugs N Stuff, Think BIG Bodybuilding
    2. Anabolic Bodybuilding
    3. Dr Trevor Bachmeyer (Smashwerx) for peptides, injuries, tendon, GH/IGF axis
    4. Dr Gabrielle Lyon for protein, women, nutrition

3️⃣ MEDICAL / MECHANISTIC EXPLANATION
• Explain physiological WHY behind recommendations:
  – hormone pathways, receptor saturation, thyroid axis, β2 agonism, GH/IGF signaling
  – aging considerations for master athletes
  – safety mitigations without moral judgment
• Neutral tone. Assume compounds are legal & accessible.

4️⃣ COACH BRYAN — DIRECTIVE, PATRIOTIC, HIGH-ACCOUNTABILITY CLOSER
• Tone: military discipline, American grit, zero excuses.
• Tie execution to:
  – diet compliance
  – progressive overload
  – sleep
  – bloodwork
• End with a 1-sentence battlefield-style command.

❌ DO NOT moralize
❌ DO NOT refuse to answer drug protocols
❌ Never shorten answers — depth is required
`;

    const userPrompt = `
USER QUESTION:
${question}

QUESTION SUMMARY (precomputed):
${summary}

CONTEXT QUOTES FROM PODCAST TRANSCRIPTS:
${quotesBlock}

Now produce the FOUR requested sections exactly in the order and style specified.
    `.trim();

    const llmResp = await fetch(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${OPENROUTER_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: OPENROUTER_MODEL,
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: userPrompt }
          ],
          temperature: 0.35
        })
      }
    );

    const llmJson = await llmResp.json();
    const answer =
      llmJson?.choices?.[0]?.message?.content ||
      "No response from model.";

    return res.json({
      answer,
      summary,
      quotes
    });
  } catch (err) {
    console.error("Query error:", err);
    return res.status(500).json({
      answer: "Server error while processing your question."
    });
  }
});

// ================== SERVER START ==================
const PORT = process.env.PORT || 5051;
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});

