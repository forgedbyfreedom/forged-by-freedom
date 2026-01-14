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

// Use fast model for stability (Wix-safe). You can upgrade later.
const MODEL = "nousresearch/hermes-3-llama-3.1-8b";

// Retrieval tuning
const TOP_K = 20;                 // higher recall
const MAX_SOURCES = 3;            // show 1–3 sources
const PER_SOURCE_LIMIT = 900;     // per quote cap
const MAX_CONTEXT_CHARS = 4500;   // total cap (prevents empty choices)
const MAX_TOKENS = 700;           // completion cap (prevents empty choices)

/* =======================
   HELPERS
======================= */
function expandQuery(q) {
  const s = (q || "").toLowerCase();
  if (s.includes("female") || s.includes("women") || s.includes("woman")) {
    return `${q}. Focus terms: women female virilization androgenic side effects trenbolone`;
  }
  return q;
}

function pickText(md) {
  if (!md) return "";
  return (
    md.text ||
    md.quote ||
    md.chunk ||
    md.content ||
    md.transcript ||
    md.body ||
    ""
  ).trim();
}

function pickEpisode(md) {
  if (!md) return "Unknown Episode";
  return (md.episode || md.title || md.video_title || md.file || "Unknown Episode").toString().trim();
}

function pickPodcast(md) {
  if (!md) return "Unknown Podcast";
  return (md.podcast || md.show || md.channel || md.source || "Unknown Podcast").toString().trim();
}

function pickSpeaker(md) {
  if (!md) return "Unknown Speaker";
  return (md.speaker || md.host || md.author || md.show || "Unknown Speaker").toString().trim();
}

/* =======================
   HEALTH CHECK
======================= */
app.get("/status", (_req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    model: MODEL,
    pineconeQueryUrl: `${PINECONE_HOST}/query`,
    time: new Date().toISOString()
  });
});

/* =======================
   ASK (OPTION A)
======================= */
app.post("/ask", async (req, res) => {
  try {
    const question = (req.body?.question || "").trim();
    if (!question) return res.status(400).json({ error: "No question provided" });

    const expanded = expandQuery(question);

    // 1) EMBEDD
    const embRes = await fetch("https://openrouter.ai/api/v1/embeddings", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "text-embedding-3-large",
        input: expanded
      })
    });

    const emb = await embRes.json();
    const vector = emb?.data?.[0]?.embedding;
    if (!vector) throw new Error("Embedding failed");

    // 2) PINECONE QUERY
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
    const matches = pc?.matches || [];

    // 3) BUILD SOURCES + CONTEXT (ALWAYS SHOW SOURCES IF FOUND)
    let used = 0;
    const sourceBlocks = [];
    const sourcesForDisplay = [];

    for (let i = 0; i < matches.length && sourceBlocks.length < MAX_SOURCES; i++) {
      const md = matches[i]?.metadata || {};
      const raw = pickText(md);
      if (!raw) continue;

      const remaining = MAX_CONTEXT_CHARS - used;
      if (remaining <= 0) break;

      const sliceLen = Math.min(PER_SOURCE_LIMIT, remaining);
      const quote = raw.slice(0, sliceLen);

      const podcast = pickPodcast(md);
      const episode = pickEpisode(md);
      const speaker = pickSpeaker(md);

      sourcesForDisplay.push({ podcast, episode, speaker, quote });

      sourceBlocks.push(
        `SOURCE ${sourceBlocks.length + 1}
Podcast: ${podcast}
Episode: ${episode}
Speaker: ${speaker}

"${quote}"`
      );

      used += quote.length;
    }

    if (sourceBlocks.length === 0) {
      return res.json({
        answer:
          "No usable quoted transcript material was retrieved for this question. Try a more specific query (compound + effect + audience)."
      });
    }

    const context = sourceBlocks.join("\n\n");

    // 4) LLM (OPTION A: Multi-source synthesis, quote-required)
    const prompt = `
You are Coach Bryan’s evidence-based assistant.

RULES (MANDATORY):
- Use ONLY the SOURCES below.
- You MAY synthesize across sources, but every factual claim MUST be supported by at least one quoted source.
- NEVER invent quotes or metadata.
- If the sources do not directly answer the question, say that clearly — but STILL show the best relevant quotes you have.

OUTPUT FORMAT (REQUIRED):

Answer:
- 2–5 sentences (quote-supported). If insufficient, state what is missing.

Sources:
- Podcast:
  Episode:
  Speaker:
  Quote: "..."

(Include 1–3 sources; quotes must be verbatim from the context.)

Explanation:
- Bullet points:
  • what the quotes establish
  • what they do not establish
  • how you connected sources (if you synthesized)

What to ask next:
- 1–2 refined follow-up questions

SOURCES:
${context}

QUESTION:
${question}
`.trim();

    const llmRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        temperature: 0.2,
        max_tokens: MAX_TOKENS,
        messages: [{ role: "user", content: prompt }]
      })
    });

    const llm = await llmRes.json();

    // Guard against empty choices
    const answer = (llm?.choices?.[0]?.message?.content || "").trim();

    if (!answer) {
      // Fallback: show sources even if the model refused
      const fallback = [
        "Answer:",
        "Insufficient quoted evidence in the database to answer this question directly.",
        "",
        "Sources:"
      ];

      sourcesForDisplay.forEach((s) => {
        fallback.push(`- Podcast: ${s.podcast}`);
        fallback.push(`  Episode: ${s.episode}`);
        fallback.push(`  Speaker: ${s.speaker}`);
        fallback.push(`  Quote: "${s.quote}"`);
      });

      fallback.push("");
      fallback.push("What to ask next:");
      fallback.push("- Ask about a specific side effect (e.g., 'trenbolone insomnia women virilization')");
      fallback.push("- Ask for 'women + tren + virilization' directly");

      return res.json({ answer: fallback.join("\n") });
    }

    return res.json({ answer });

  } catch (err) {
    return res.status(500).json({
      error: "AI backend failure",
      details: err.message
    });
  }
});

app.listen(PORT || 5051, () => {
  console.log(`[FBF API] running on port ${PORT || 5051} using ${MODEL}`);
});
