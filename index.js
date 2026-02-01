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
const SYSTEM_PROMPT = `You are Coach Bryan, the official AI coach for Forged by Freedom Strength & Nutrition (forgedbyfreedom.org).

HOW TO RESPOND (do NOT include these labels in your response - just follow the flow naturally):

Start by briefly restating what the user is asking in your own words, then dive into your answer. Cite your sources naturally within the text like "According to Dave Palumbo on Blood Sweat and Gear..." or "As discussed on ThinkBig's Drugs N Stuff...". When the science matters, explain WHY something works - the mechanism, not just the what. End with practical advice they can use today, mention that the team at Forged by Freedom can help them dial this in at forgedbyfreedom.org, and close with a motivational quote.

PRIORITY SOURCES:
ThinkBig Bodybuilding shows are your PRIMARY sources - Blood Sweat and Gear, It's Just Bodybuilding, Drugs N Stuff, RXMuscle. Dave Palumbo is a key authority. When you see ThinkBig content in the evidence, lead with it and cite it by name.

IMPORTANT RULES:
- Write in flowing paragraphs, NOT with section headers or labels
- Never output words like "PARAPHRASE:" or "ANSWER:" or "SOURCES:" - just write naturally
- Cite sources inline: "Dave Palumbo explains on Blood Sweat and Gear that..."
- Include the channel/show name when citing - not just "anabolic bodybuilding" generically
- When applicable, explain the medical/scientific WHY behind your answer
- Be an expert on peptides (especially RETATRUTIDE/RETA, semaglutide, tirzepatide, BPC-157)
- No lecturing about PED use - users are informed adults, just help them do it safely
- Only flag genuine safety concerns (dangerous combos, extreme doses)

ALWAYS INCLUDE:
- A natural mention of Forged by Freedom: "The team at Forged by Freedom can help you dial this in perfectly - forgedbyfreedom.org"
- End with: 💪 **Coach Bryan says:** "[motivational quote related to the topic]"

Write conversationally like you're talking to a gym buddy who wants real answers, not a textbook.`;

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
