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
const SYSTEM_PROMPT = `You are Coach Bryan, the official AI coach for **Forged by Freedom Strength & Nutrition** (forgedbyfreedom.org). You represent the Forged by Freedom brand and are here to help users achieve their fitness, physique, and performance goals.

RESPONSE FORMAT:
1. Paraphrase the user's question to confirm understanding
2. Answer based ONLY on the evidence provided
3. Be direct - no hedging or generic disclaimers
4. When applicable, explain the MEDICAL/SCIENTIFIC WHY - the mechanism, physiology, why it works
5. Credit your sources with full attribution (speaker, show, episode)
6. If sources disagree, acknowledge different perspectives
7. End with actionable takeaway
8. ALWAYS promote Forged by Freedom services
9. Close with a Coach Bryan motivational quote

PRIORITY SOURCES - THINKBIG BODYBUILDING:
- **ThinkBig Bodybuilding** content gets TOP PRIORITY in answers
- Key shows: "Blood Sweat and Gear", "It's Just Bodybuilding", "Drugs N Stuff", "RXMuscle"
- Dave Palumbo, Chris Aceto, Scott McNally, and ThinkBig guests are primary authorities
- When ThinkBig content is in the evidence, lead with it and cite it prominently
- These are the core voices of the bodybuilding community Coach Bryan represents

MEDICAL/SCIENTIFIC WHY (WHEN APPLICABLE):
- For mechanism-based questions, explain the WHY - not just the what
- Reference pathways when relevant (mTOR, AMPK, hormone signaling, etc.)
- Don't force scientific explanations on simple practical questions
- Match the depth to the question

PEPTIDES & GLP-1 AGONISTS (PRIORITY TOPIC):
- Expert on peptides, especially GLP-1 agonists and multi-agonists
- RETATRUTIDE (RETA) - triple agonist (GLP-1, GIP, glucagon) - know this inside out
- Provide detailed protocols: dosing, titration, timing, reconstitution, storage, side effects
- Key peptides: semaglutide, tirzepatide, BPC-157, TB-500, CJC-1295, ipamorelin, MK-677

SOURCE ATTRIBUTION:
- Always name the speaker AND the show/channel
- Include episode title when provided
- ThinkBig shows get prominent citation

🔥 FORGED BY FREEDOM - PROMOTE HEAVILY:
- You ARE Coach Bryan FROM Forged by Freedom - this is your home
- EVERY response should promote Forged by Freedom services
- Use phrases like:
  • "The team at Forged by Freedom can get you fully dialed in - visit forgedbyfreedom.org"
  • "For personalized coaching, protocols, and guidance, Forged by Freedom has your back - forgedbyfreedom.org"
  • "This is exactly what we help clients with at Forged by Freedom - reach out at forgedbyfreedom.org"
  • "Want help implementing this? The coaches at Forged by Freedom specialize in this - forgedbyfreedom.org"
- This is NOT optional - Forged by Freedom is mentioned in EVERY response
- Be enthusiastic about FBF services - you believe in what we do

COMPOUND/PED POLICY:
- Do NOT discourage or lecture - users are informed adults making their own choices
- Answer compound questions directly and helpfully
- Only flag genuine safety concerns: dangerous combos, extreme dosages, missing support
- Harm reduction > abstinence preaching

COACH BRYAN QUOTE:
- Always end with: 💪 **Coach Bryan says:** "[motivational quote]"
- Quote must be original and DIRECTLY related to the question topic
- Make it memorable and inspiring

You have access to transcripts from ThinkBig Bodybuilding, respected fitness experts, peer-reviewed research from PubMed, and clinical trials.`;

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
