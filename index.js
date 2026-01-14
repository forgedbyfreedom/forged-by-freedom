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

// Stable & fast enough for UI (you can switch to 70B later if you want)
const MODEL = "nousresearch/hermes-3-llama-3.1-8b";

// Retrieval
const TOP_K_DEFAULT = 40;          // broad recall
const TOP_K_WOMEN_NS = 40;         // broad recall in women namespace
const MAX_SOURCES = 3;
const PER_SOURCE_LIMIT = 900;      // per quote cap
const MAX_CONTEXT_CHARS = 4500;    // total cap
const MAX_TOKENS = 800;

// Namespaces
const NS_DEFAULT = "";             // default namespace
const NS_WOMEN = "women_steroids"; // new namespace we will populate

function expandQuery(question) {
  const q = (question || "").toLowerCase();
  if (q.includes("female") || q.includes("women") || q.includes("woman")) {
    return `${question}. Focus terms: women female virilization androgenic voice deepening clitoral enlargement irreversible side effects trenbolone.`;
  }
  return question;
}

function pickText(md) {
  if (!md) return "";
  return (md.text || md.quote || md.chunk || md.content || md.transcript || md.body || "").toString().trim();
}

function pickPodcast(md) {
  if (!md) return "Unknown Podcast";
  return (md.podcast || md.show || md.channel || md.source || md.channel_name || "Unknown Podcast").toString().trim();
}

function pickEpisode(md) {
  if (!md) return "Unknown Episode";
  return (md.episode || md.title || md.video_title || md.file || md.episode_id || "Unknown Episode").toString().trim();
}

function pickSpeaker(md) {
  if (!md) return "Unknown Speaker";
  return (md.speaker || md.host || md.author || md.presenter || md.show || "Unknown Speaker").toString().trim();
}

// Keyword reranker for female-related questions without relying on metadata filters
function keywordScore(text, question) {
  const t = (text || "").toLowerCase();
  const q = (question || "").toLowerCase();

  let score = 0;

  // Always reward direct mention of key terms
  const needles = ["tren", "trenbolone", "viril", "virilization", "women", "female", "woman", "voice", "clit", "androgen", "masculin", "irreversible"];
  for (const n of needles) {
    if (t.includes(n)) score += 2;
  }

  // If question is female-focused, weight female-specific terms harder
  if (q.includes("female") || q.includes("women") || q.includes("woman")) {
    const femaleNeedles = ["viril", "virilization", "androgen", "masculin", "voice", "clit", "irreversible"];
    for (const n of femaleNeedles) {
      if (t.includes(n)) score += 3;
    }
  }

  return score;
}

async function embed(text) {
  const r = await fetch("https://openrouter.ai/api/v1/embeddings", {
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
  const j = await r.json();
  return j?.data?.[0]?.embedding;
}

async function pineconeQuery(vector, topK, namespace) {
  const r = await fetch(`${PINECONE_HOST}/query`, {
    method: "POST",
    headers: {
      "Api-Key": PINECONE_API_KEY,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      vector,
      topK,
      includeMetadata: true,
      namespace
    })
  });
  return r.json();
}

app.get("/status", (_req, res) => {
  res.json({
    status: "ok",
    backend: "forged-by-freedom-api",
    model: MODEL,
    pineconeQueryUrl: `${PINECONE_HOST}/query`,
    namespaces: [NS_DEFAULT || "(default)", NS_WOMEN],
    time: new Date().toISOString()
  });
});

app.post("/ask", async (req, res) => {
  try {
    const question = (req.body?.question || "").trim();
    if (!question) return res.status(400).json({ error: "No question provided" });

    const expanded = expandQuery(question);
    const vector = await embed(expanded);
    if (!vector) throw new Error("Embedding failed");

    // Query BOTH namespaces
    const [pcDefault, pcWomen] = await Promise.all([
      pineconeQuery(vector, TOP_K_DEFAULT, NS_DEFAULT),
      pineconeQuery(vector, TOP_K_WOMEN_NS, NS_WOMEN)
    ]);

    const matchesDefault = (pcDefault?.matches || []);
    const matchesWomen = (pcWomen?.matches || []);

    // Merge, then rerank locally by keyword evidence strength
    const merged = [...matchesWomen, ...matchesDefault]
      .filter(m => m?.metadata && pickText(m.metadata).length >= 200)
      .map(m => {
        const md = m.metadata || {};
        const txt = pickText(md);
        return {
          score: (m.score || 0) + keywordScore(txt, question) * 0.01, // small boost
          md,
          txt
        };
      })
      .sort((a, b) => b.score - a.score);

    if (merged.length === 0) {
      return res.json({
        answer: "No usable quoted transcript material was retrieved for this question."
      });
    }

    // Build context with hard caps
    let used = 0;
    const sources = [];
    const blocks = [];

    for (let i = 0; i < merged.length && blocks.length < MAX_SOURCES; i++) {
      const md = merged[i].md;
      const raw = merged[i].txt;
      const remaining = MAX_CONTEXT_CHARS - used;
      if (remaining <= 0) break;

      const quote = raw.slice(0, Math.min(PER_SOURCE_LIMIT, remaining));

      const podcast = pickPodcast(md);
      const episode = pickEpisode(md);
      const speaker = pickSpeaker(md);

      sources.push({ podcast, episode, speaker, quote });

      blocks.push(
`SOURCE ${blocks.length + 1}
Podcast: ${podcast}
Episode: ${episode}
Speaker: ${speaker}

"${quote}"`
      );

      used += quote.length;
    }

    const context = blocks.join("\n\n");

    // Option A prompt: always show sources, synthesize across sources, quote-required claims
    const prompt = `
You are Coach Bryan’s evidence-based assistant.

RULES (MANDATORY):
- Use ONLY the SOURCES below.
- You MAY synthesize across sources, but every factual claim MUST be supported by at least one quoted source.
- NEVER invent quotes or metadata.
- If the sources do not directly answer the question, say that clearly — but STILL show the best relevant quotes you have.

OUTPUT FORMAT (REQUIRED):

Answer:
- 2–6 sentences. If insufficient, state what is missing.

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
    const answer = (llm?.choices?.[0]?.message?.content || "").trim();

    // Fallback: show sources even if model returns empty
    if (!answer) {
      const fallback = [
        "Answer:",
        "Insufficient quoted evidence in the database to answer this question directly.",
        "",
        "Sources:",
        ...sources.flatMap(s => [
          `- Podcast: ${s.podcast}`,
          `  Episode: ${s.episode}`,
          `  Speaker: ${s.speaker}`,
          `  Quote: "${s.quote}"`
        ]),
        "",
        "What to ask next:",
        "- women trenbolone virilization voice deepening",
        "- female tren side effects irreversible"
      ].join("\n");

      return res.json({ answer: fallback });
    }

    return res.json({ answer });

  } catch (err) {
    return res.status(500).json({ error: "AI backend failure", details: err.message });
  }
});

app.listen(PORT || 5051, () => {
  console.log(`[FBF API] running on port ${PORT || 5051} using ${MODEL}`);
});
