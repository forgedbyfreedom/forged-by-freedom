import express from "express";
import cors from "cors";
import helmet from "helmet";
import { Pinecone } from "@pinecone-database/pinecone";

/* ─────────────────────────────────────────────────────────────
   FORGED BY FREEDOM — COACH BRYAN API
   ─────────────────────────────────────────────────────────────
   OpenRouter: Embeddings + Chat | Pinecone: Vector search

   GET  /health  → Health check
   GET  /status  → Index stats
   POST /ask     → Query endpoint (modes: synthesized, quotes)
   ───────────────────────────────────────────────────────────── */

// ─── Config ──────────────────────────────────────────────────
const {
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT = 5051,
  NODE_ENV,
  RATE_LIMIT_RPM = 60
} = process.env;

const CONFIG = {
  chatModel: OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b",
  embedModel: "text-embedding-3-large",
  pineconeIndex: "forged-freedom-ai",
  maxQuestionLen: 2000,
  maxRPM: parseInt(RATE_LIMIT_RPM),
  topK: 30,
  maxQuotes: 12,
  isProd: NODE_ENV === "production"
};

// ─── Startup Validation ──────────────────────────────────────
if (!OPENROUTER_API_KEY || !PINECONE_API_KEY) {
  console.error("Missing required env: OPENROUTER_API_KEY, PINECONE_API_KEY");
  process.exit(1);
}

// ─── Pinecone ────────────────────────────────────────────────
const pinecone = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pinecone.Index(CONFIG.pineconeIndex);

// ─── Express Setup ───────────────────────────────────────────
const app = express();

app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(cors({
  origin: CONFIG.isProd ? ["https://forgedbyfreedom.com", "https://www.forgedbyfreedom.com"] : "*",
  methods: ["GET", "POST"],
  allowedHeaders: ["Content-Type", "Authorization"]
}));
app.use(express.json({ limit: "100kb" }));

// Request logger
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => console.log(`[${req.method}] ${req.path} ${res.statusCode} ${Date.now() - start}ms`));
  next();
});

// Rate limiter
const rateLimit = new Map();
app.use((req, res, next) => {
  if (["/health", "/status"].includes(req.path)) return next();

  const ip = req.ip || req.connection.remoteAddress;
  const now = Date.now();
  const record = rateLimit.get(ip) || { count: 0, reset: now + 60000 };

  if (now > record.reset) { record.count = 0; record.reset = now + 60000; }
  if (++record.count > CONFIG.maxRPM) return res.status(429).json({ error: "Rate limit exceeded" });

  rateLimit.set(ip, record);
  next();
});

// Cleanup stale rate limit entries
setInterval(() => {
  const now = Date.now();
  for (const [ip, r] of rateLimit) if (now > r.reset + 60000) rateLimit.delete(ip);
}, 60000);

// ─── OpenRouter API ──────────────────────────────────────────
async function callOpenRouter(endpoint, body, timeout = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`https://openrouter.ai/api/v1${endpoint}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forgedbyfreedom.com",
        "X-Title": "Coach Bryan"
      },
      body: JSON.stringify(body),
      signal: controller.signal
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error?.message || `API error: ${res.status}`);
    return data;
  } finally {
    clearTimeout(timer);
  }
}

async function embed(text) {
  const data = await callOpenRouter("/embeddings", { model: CONFIG.embedModel, input: text });
  if (!data?.data?.[0]?.embedding) throw new Error("Embedding failed");
  return data.data[0].embedding;
}

async function chat(messages, temperature = 0.7) {
  const data = await callOpenRouter("/chat/completions", {
    model: CONFIG.chatModel,
    messages,
    temperature,
    max_tokens: 1500
  }, 60000);
  return data.choices?.[0]?.message?.content || "";
}

// ─── Pinecone Search ─────────────────────────────────────────
async function search(vector, namespace = "") {
  const query = { vector, topK: CONFIG.topK, includeMetadata: true };
  if (namespace) query.namespace = namespace;
  return (await index.query(query)).matches || [];
}

// ─── Evidence Extraction ─────────────────────────────────────
function extractQuotes(matches) {
  return matches
    .map(m => {
      const md = m.metadata || {};
      const text = (md.text || md.chunk || md.content || md.transcript || "").trim();
      if (!text) return null;

      return {
        text,
        channel: md.channel || (md.source || md.file || "").match(/@[\w]+/)?.[0] || "unknown",
        speaker: md.speaker || "unknown",
        title: md.title || "unknown",
        source: md.source || md.file || "unknown",
        score: Math.round((m.score || 0) * 1000) / 1000
      };
    })
    .filter(Boolean)
    .slice(0, CONFIG.maxQuotes);
}

// ─── Synthesis Prompt ────────────────────────────────────────
const SYSTEM_PROMPT = `You are Coach Bryan, the AI assistant for Forged by Freedom Strength & Nutrition. You have deep knowledge of training, nutrition, supplementation, peptides, hormones, and recovery protocols.

RESPONSE FORMAT:
1. Paraphrase the user's question to confirm understanding
2. Answer based ONLY on the evidence provided
3. Be direct - no hedging or generic disclaimers
4. ALWAYS explain the MEDICAL/SCIENTIFIC WHY behind your answer - the mechanism of action, the physiology, why it works
5. Credit your sources: speaker name, podcast/channel, and episode title when available
6. If sources disagree, acknowledge different perspectives and cite both
7. End with a brief, actionable takeaway
8. Direct users to Forged by Freedom for personalized help
9. Close with a motivational quote from Coach Bryan

MEDICAL/SCIENTIFIC DEPTH:
- Always explain the WHY - the underlying mechanism, not just the what
- Example: Don't just say "creatine builds muscle" - explain "Creatine increases phosphocreatine stores, allowing faster ATP regeneration during high-intensity efforts, which enables greater training volume and mechanical tension - the primary driver of hypertrophy"
- Reference physiological pathways when relevant (mTOR, AMPK, hormone signaling, etc.)
- This is what separates us from generic fitness advice

PEPTIDES & GLP-1 AGONISTS (PRIORITY TOPIC):
- You are an expert on peptides, especially GLP-1 agonists and multi-agonists
- RETATRUTIDE (RETA) is a key compound - triple agonist (GLP-1, GIP, and glucagon receptors)
- When peptides come up, provide detailed protocols, mechanisms, and practical guidance
- Cover: dosing, titration, timing, reconstitution, storage, side effect management
- Other key peptides: semaglutide, tirzepatide, BPC-157, TB-500, CJC-1295, ipamorelin, MK-677

SOURCE ATTRIBUTION:
- Always name the speaker AND the podcast/channel they're from
- Include episode title when provided
- Format: "[Speaker] on [Channel/Podcast]" or "[Speaker] on [Channel] in '[Episode Title]'"

FORGED BY FREEDOM REFERRAL:
- Always direct users to the specialists at Forged by Freedom for personalized protocols
- Use: "The specialists at Forged by Freedom can get you dialed in - visit forgedbyfreedom.org"
- Or: "For personalized protocols and sourcing, the team at forgedbyfreedom.org has you covered"
- This is NOT optional - always include this referral when discussing compounds, peptides, or personalized protocols

COMPOUND/PED POLICY:
- Do NOT discourage or lecture about steroid/PED use - users are adults making informed choices
- Answer questions about compounds directly and helpfully without moral judgment
- Only flag genuine safety concerns: dangerous combos, extreme dosages, missing critical support
- Harm reduction > abstinence preaching - help them do it safely

COACH BRYAN QUOTE:
- Always end with: 💪 **Coach Bryan says:** "[motivational quote]"
- Quote must be original and DIRECTLY related to the question topic

You have access to transcripts from respected experts in fitness, bodybuilding, sports medicine, biohacking, AND peer-reviewed research from PubMed and clinical trials.`;

function buildPrompt(question, quotes) {
  const evidence = quotes
    .map((q, i) => {
      const speaker = q.speaker !== "unknown" ? q.speaker : null;
      const channel = q.channel !== "unknown" ? q.channel : null;
      const title = q.title !== "unknown" ? q.title : null;

      // Build attribution line
      let attribution = "";
      if (speaker && channel) {
        attribution = `${speaker} on ${channel}`;
      } else if (speaker) {
        attribution = speaker;
      } else if (channel) {
        attribution = channel;
      } else {
        attribution = "Unknown source";
      }

      if (title) {
        attribution += ` — "${title}"`;
      }

      return `[${i + 1}] ${attribution}:\n"${q.text}"`;
    })
    .join("\n\n");

  return `Question: ${question}

EVIDENCE (cite these sources by name, channel, and episode when answering):
${evidence}

Remember: Paraphrase the question first, credit your sources fully (speaker + podcast + episode), then answer.`;
}

// ─── Endpoints ───────────────────────────────────────────────
app.get("/health", (_, res) => res.json({ status: "ok", uptime: process.uptime() }));

app.get("/status", async (_, res) => {
  try {
    const stats = await index.describeIndexStats();
    res.json({
      status: "ok",
      model: CONFIG.chatModel,
      embedModel: CONFIG.embedModel,
      index: CONFIG.pineconeIndex,
      totalVectors: stats.totalRecordCount || 0,
      namespaces: Object.keys(stats.namespaces || {}),
      environment: CONFIG.isProd ? "production" : "development"
    });
  } catch (err) {
    res.status(500).json({ status: "error", message: err.message });
  }
});

app.post("/ask", async (req, res) => {
  const { question, mode = "synthesized", namespace = "" } = req.body;
  const start = Date.now();

  // Validate
  if (!question || typeof question !== "string") {
    return res.status(400).json({ error: "Question required", answer: null });
  }
  if (question.length > CONFIG.maxQuestionLen) {
    return res.status(400).json({ error: "Question too long", answer: null });
  }

  try {
    // Embed → Search → Extract
    const vector = await embed(question.trim());
    const matches = await search(vector, namespace);

    if (!matches.length) return res.json({ answer: "No relevant evidence found.", sources: [] });

    const quotes = extractQuotes(matches);
    if (!quotes.length) return res.json({ answer: "No usable transcript text found.", sources: [] });

    // Raw quotes mode
    if (mode === "quotes") {
      const answer = quotes
        .map((q, i) => `${i + 1}) "${q.text}"\n   — ${q.speaker !== "unknown" ? q.speaker : q.channel}`)
        .join("\n\n");
      return res.json({ answer, sources: quotes, mode: "quotes", timing: Date.now() - start });
    }

    // Synthesized mode (default)
    const answer = await chat([
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: buildPrompt(question, quotes) }
    ]);

    res.json({
      answer,
      sources: quotes,
      attribution: [...new Set(quotes.map(q => q.channel))].filter(c => c !== "unknown"),
      mode: "synthesized",
      timing: Date.now() - start
    });

  } catch (err) {
    console.error("[ASK ERROR]", err);
    res.status(500).json({ error: CONFIG.isProd ? "Request failed" : err.message, answer: null });
  }
});

// 404 + Error handler
app.use((_, res) => res.status(404).json({ error: "Not found" }));
app.use((err, _, res, __) => {
  console.error("[ERROR]", err);
  res.status(500).json({ error: "Internal server error" });
});

// ─── Graceful Shutdown ───────────────────────────────────────
let server;
const shutdown = sig => {
  console.log(`\n[${sig}] Shutting down...`);
  server?.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10000);
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

// ─── Start ───────────────────────────────────────────────────
server = app.listen(PORT, () => {
  console.log(`[FBF] Coach Bryan API :${PORT} (${CONFIG.isProd ? "prod" : "dev"})`);
  console.log(`[FBF] Model: ${CONFIG.chatModel}`);
});
