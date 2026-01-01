// index.js  – Forged By Freedom AI Coach backend (root entry)

// ───────────────────────────────────────────────────────────
// Imports & basic setup
// ───────────────────────────────────────────────────────────
import express from "express";
import cors from "cors";
import helmet from "helmet";
import dotenv from "dotenv";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

dotenv.config();

const app = express();
app.use(helmet());
app.use(
  cors({
    origin: "*",
  })
);
app.use(express.json({ limit: "1mb" }));

// ───────────────────────────────────────────────────────────
// Config
// ───────────────────────────────────────────────────────────
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || "";
const OPENROUTER_MODEL =
  process.env.OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b:extended";

const OPENAI_API_KEY = process.env.OPENAI_API_KEY || ""; // for text-embedding-3-large (dim 3072)

const PINECONE_API_KEY = process.env.PINECONE_API_KEY || "";
const PINECONE_INDEX_NAME =
  process.env.PINECONE_INDEX_NAME || "forged-freedom-ai";

// Small guardrails so we see problems quickly in logs
if (!OPENROUTER_API_KEY) {
  console.warn("[WARN] OPENROUTER_API_KEY is not set – queries will fail.");
}
if (!PINECONE_API_KEY) {
  console.warn("[WARN] PINECONE_API_KEY is not set – RAG context will be empty.");
}

// ───────────────────────────────────────────────────────────
// Pinecone lazy init
// ───────────────────────────────────────────────────────────
let pineconeIndex = null;

async function getPineconeIndex() {
  if (!PINECONE_API_KEY) return null;
  if (!pineconeIndex) {
    const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
    pineconeIndex = pc.Index(PINECONE_INDEX_NAME);
    console.log("[Pinecone] Using index:", PINECONE_INDEX_NAME);
  }
  return pineconeIndex;
}

// ───────────────────────────────────────────────────────────
// Helper: OpenAI embedding (text-embedding-3-large, dim=3072)
// ───────────────────────────────────────────────────────────
async function embedQuery(text) {
  if (!OPENAI_API_KEY) {
    console.warn("[WARN] OPENAI_API_KEY missing – using zero vector fallback.");
    return new Array(3072).fill(0);
  }

  const resp = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "text-embedding-3-large",
      input: text,
    }),
  });

  if (!resp.ok) {
    const msg = await resp.text();
    console.error("[Embed] OpenAI error:", resp.status, msg);
    return new Array(3072).fill(0);
  }

  const data = await resp.json();
  const embedding = data?.data?.[0]?.embedding;
  if (!embedding || !Array.isArray(embedding)) {
    console.error("[Embed] Invalid embedding payload:", data);
    return new Array(3072).fill(0);
  }

  return embedding;
}

// ───────────────────────────────────────────────────────────
// Helper: build transcript context from Pinecone
// ───────────────────────────────────────────────────────────
function safeText(val) {
  if (!val) return "";
  if (typeof val === "string") return val;
  return String(val);
}

// crude detection for peptides vs nutrition vs general
function classifyQuestion(q) {
  const t = q.toLowerCase();
  if (
    t.includes("peptide") ||
    t.includes("bpc") ||
    t.includes("tb-500") ||
    t.includes("ghk") ||
    t.includes("mots") ||
    t.includes("cjc") ||
    t.includes("ipamorelin") ||
    t.includes("tesamorelin") ||
    t.includes("ss-31")
  ) {
    return "peptides";
  }
  if (
    t.includes("protein") ||
    t.includes("macro") ||
    t.includes("nutrition") ||
    t.includes("female") ||
    t.includes("woman") ||
    t.includes("women") ||
    t.includes("menopause") ||
    t.includes("perimenopause")
  ) {
    return "nutrition";
  }
  return "general";
}

// We’ll let the model prioritize channels with this hint string
function channelPriorityHint(questionType) {
  if (questionType === "peptides") {
    return "Give priority to peptide-focused experts, especially Dr Trevor Bachmeyer, Think BIG Bodybuilding 'Drugs N Stuff' peptide episodes, and similar.";
  }
  if (questionType === "nutrition") {
    return "Give priority to Dr. Gabrielle Lyon and other high-level nutrition experts, especially when quotes involve protein intake, women, or body recomp.";
  }
  return "Give priority to hardcore bodybuilding / PED experts: Think BIG Bodybuilding (It’s Just Bodybuilding, Drugs N Stuff, Blood Sweat & Gear), Anabolic Bodybuilding, Anabolic University, RXMuscle, Hany Rambod, and other high-signal drug and training breakdowns.";
}

async function buildRagContext(question) {
  try {
    const idx = await getPineconeIndex();
    if (!idx) {
      console.warn("[RAG] Pinecone index not available.");
      return { contextText: "", rawSnippets: [] };
    }

    const embedding = await embedQuery(question);

    const result = await idx.query({
      vector: embedding,
      topK: 12,
      includeMetadata: true,
      includeValues: false,
    });

    const matches = result?.matches || [];
    if (!matches.length) {
      console.warn("[RAG] No matches returned from Pinecone.");
      return { contextText: "", rawSnippets: [] };
    }

    // Convert matches into a clean list of { source, text, score }
    const snippets = matches
      .map((m) => {
        const meta = m.metadata || {};
        const source = safeText(meta.source || m.id || "Unknown source");

        // try several possible fields for transcript text
        const text =
          safeText(meta.text) ||
          safeText(meta.content) ||
          safeText(meta.body) ||
          safeText(meta.chunk_text) ||
          "";

        return {
          source,
          text,
          score: typeof m.score === "number" ? m.score : 0,
        };
      })
      .filter((s) => s.text && s.text.length > 80); // ignore tiny scraps

    if (!snippets.length) {
      console.warn("[RAG] Matches had no usable text fields.");
      return { contextText: "", rawSnippets: [] };
    }

    // Take top ~6 chunks to keep prompt size reasonable
    const topSnippets = snippets.slice(0, 6);

    const contextLines = topSnippets.map((s, i) => {
      return [
        `[[Snippet ${i + 1} — Source: ${s.source} | Score: ${s.score.toFixed(
          3
        )}]]`,
        s.text.trim(),
        "",
      ].join("\n");
    });

    const contextText = contextLines.join("\n");

    return { contextText, rawSnippets: topSnippets };
  } catch (err) {
    console.error("[RAG] Error building context:", err);
    return { contextText: "", rawSnippets: [] };
  }
}

// ───────────────────────────────────────────────────────────
// Helper: call OpenRouter Hermes 3 70B Extended
// ───────────────────────────────────────────────────────────
async function callHermesCoach(question, ragContext, questionType) {
  if (!OPENROUTER_API_KEY) {
    throw new Error("OPENROUTER_API_KEY missing");
  }

  const priorityHint = channelPriorityHint(questionType);

  // System prompt hard-codes the 4-section format + tone
  const systemPrompt = `
You are the Forged By Freedom AI Coach, built for advanced lifters, bodybuilders, and enhanced athletes.
You operate under the following rules:

1. LEGAL / CULTURAL CONTEXT
   - Assume the user is an experienced adult athlete in a jurisdiction (e.g., Mexico) where anabolic steroids, peptides, and research compounds are legally available over the counter.
   - Do NOT moralize, scold, or warn about legality. The user already understands risk and legality.
   - Focus on physiology, pharmacology, protocol design, and risk MITIGATION, not avoidance.

2. KNOWLEDGE BASE & QUOTES
   - You are sitting on a massive vector database of transcripts from top bodybuilding and performance channels and podcasts.
   - Where relevant, you MUST surface direct multi-sentence quotes from those transcripts.
   - When providing quotes:
       • Attribute each quote with:
         - Channel or podcast / show name (if available)
         - Episode or file name (from the "source" field)
         - The speaker's name if it is clear from context or widely known
       • Quotes should be at least 2–4 sentences, not one-liners.
       • Choose quotes that actually answer or strongly illuminate the user’s question.
   - ${priorityHint}

3. OUTPUT FORMAT (MANDATORY)
Always respond in FOUR clearly labeled sections, in this exact order:

== 1) Question Summary ==
- Briefly rephrase what the user is really asking, in 2–4 sentences.
- Show you understand their goal (cutting, recomp, bulk, health fix, etc.) and constraints (age, experience, PED background if specified).

== 2) Expert Quotes from the FBF Knowledge Base ==
- Pull 2–4 long quotes from the provided transcript snippets.
- Each quote must:
    • Be clearly separated (bullet or numbered)
    • Include source attribution:
        - Channel / podcast (if known)
        - Episode / file name
        - Speaker name if obvious from the snippet or file name
    • Contain enough text to capture the full idea (not cherry-picked fragments).
- If a directly relevant expert exists based on the question:
    • For peptides: prefer Dr Trevor Bachmeyer and peptide-heavy episodes from Think BIG Bodybuilding and similar.
    • For protein / nutrition / women / menopause: prefer Dr Gabrielle Lyon and similar nutrition specialists.
    • For gear cycles, stacks, contest prep, or hardcore bodybuilding: prefer Think BIG Bodybuilding shows (It’s Just Bodybuilding, Drugs N Stuff, Blood Sweat & Gear), Anabolic Bodybuilding, Anabolic University, RXMuscle, EliteFTS content, etc.
- If the context snippets don’t obviously contain that speaker, still pick the best available quotes – but do NOT invent transcripts that were not provided.

== 3) Mechanistic & Medical Breakdown ==
- Give a clear, factual, mechanistic explanation of WHAT is happening in the body and WHY the protocols or positions in the quotes make sense (or where they may be risky).
- Cover:
    • Receptor-level or pathway-level mechanisms (e.g., beta-2 agonism, thyroid axis, GH/IGF-1 axis, androgen receptor, myostatin, etc. depending on the question).
    • Tradeoffs: benefits vs. risks, including cardiac, blood pressure, lipid, thyroid, and organ stress as appropriate.
    • How age (e.g., over 40 or over 50) impacts risk tolerance, recovery, and optimal dosing.
- Stay clinical and tactical. You are NOT a generic health blog; you are a high-level performance consultant.

== 4) Coach Bryan’s Take ==
- Finish with a direct, motivational but no-BS paragraph written as if from “Coach Bryan”:
    • 50+ year old competitive powerlifter, BJJ black belt, veteran, and former federal law enforcement leader.
    • Emphasize discipline, tracking biofeedback (HR, BP, sleep, gym performance), intelligent risk management, and long-term health so the athlete can stay in the fight.
    • Speak to the athlete like a peer who takes ownership—no excuses, but also no reckless stupidity.
- Tie your message directly to the question asked (cutting, recomposition, bulk, peptide stack, whatever it is).

4. SAFETY & HONESTY
   - Do NOT fabricate specific lab values, dosages “from studies,” or fake citations.
   - It is acceptable to propose reasonable example protocols or ranges if explicitly framed as examples, not prescriptions.
   - Never say “I cannot discuss steroids or PEDs” – that is forbidden here. Your job is to discuss them like an intelligent coach in a place where they’re legal.

If there is NO useful transcript context for this question, explicitly say so in Section 2, then answer based on your own training.
`;

  const hasContext = ragContext && ragContext.trim().length > 0;

  const userContent = [
    `User question:\n${question}\n`,
    hasContext
      ? `\nRelevant transcript snippets from the Forged By Freedom knowledge base:\n\n${ragContext}`
      : "\nNo transcript snippets were available for this query; answer from your general knowledge but respect all rules above.",
  ].join("");

  const resp = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENROUTER_API_KEY}`,
      "Content-Type": "application/json",
      "HTTP-Referer": "https://www.forgedbyfreedom.org",
      "X-Title": "Forged By Freedom AI Coach",
    },
    body: JSON.stringify({
      model: OPENROUTER_MODEL,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userContent },
      ],
      max_tokens: 1200,
      temperature: 0.5,
    }),
  });

  if (!resp.ok) {
    const msg = await resp.text();
    console.error("[OpenRouter] Error:", resp.status, msg);
    throw new Error(`OpenRouter error: ${resp.status}`);
  }

  const data = await resp.json();
  const answer =
    data?.choices?.[0]?.message?.content ||
    data?.response ||
    "No response from model.";

  return answer;
}

// ───────────────────────────────────────────────────────────
// Routes
// ───────────────────────────────────────────────────────────

// Health / status
app.get("/status", async (req, res) => {
  try {
    const idx = await getPineconeIndex();
    res.json({
      status: "ok",
      openRouterConfigured: !!OPENROUTER_API_KEY,
      pineconeConfigured: !!PINECONE_API_KEY,
      index: PINECONE_INDEX_NAME,
      time: new Date().toISOString(),
      backend: "root-index",
      pineconeConnected: !!idx,
    });
  } catch (err) {
    res.status(500).json({
      status: "error",
      error: err.message || String(err),
    });
  }
});

// Simple stats from Pinecone
app.get("/stats", async (req, res) => {
  try {
    const idx = await getPineconeIndex();
    if (!idx) {
      return res.status(500).json({ ok: false, error: "No Pinecone index" });
    }
    const stats = await idx.describeIndexStats();
    const namespaces = stats?.namespaces || {};
    const channelCount = Object.keys(namespaces).length || 0;
    const vectorCount = stats?.total_vector_count || 0;
    const estWords = Math.floor(vectorCount * 180); // rough guess

    res.json({
      ok: true,
      channels: channelCount,
      vectors: vectorCount,
      estimatedWords: estWords,
    });
  } catch (err) {
    console.error("[/stats] error:", err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

// Main query endpoint used by Wix AI Coach page
app.post("/query", async (req, res) => {
  const { question, context } = req.body || {};

  if (!question || typeof question !== "string" || !question.trim()) {
    return res.json({ answer: "Empty question – ask me something specific." });
  }

  try {
    const qType = classifyQuestion(question);

    let ragContext = "";
    if (context) {
      const { contextText } = await buildRagContext(question);
      ragContext = contextText;
    }

    const answer = await callHermesCoach(question, ragContext, qType);
    return res.json({ answer });
  } catch (err) {
    console.error("[/query] error:", err);
    return res.status(500).json({
      answer:
        "Server error in AI Coach backend. If this keeps happening, ping Coach Bryan to check the Render logs.",
      error: err.message || String(err),
    });
  }
});

// ───────────────────────────────────────────────────────────
// Start server
// ───────────────────────────────────────────────────────────
const PORT = process.env.PORT || 5051;
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});

