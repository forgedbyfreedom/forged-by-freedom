import express from "express";
import cors from "cors";
import helmet from "helmet";
import { Pinecone } from "@pinecone-database/pinecone";

/* ============================================================
   FORGED BY FREEDOM — COACH BRYAN API
   ============================================================
   OpenRouter: Embeddings + Chat completion
   Pinecone: Vector search

   Endpoints:
   - GET  /health   → Health check
   - GET  /status   → Index stats
   - POST /ask      → Main query endpoint
============================================================ */

/* =========================
   CONFIG
========================= */
const {
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  PORT,
  NODE_ENV,
  RATE_LIMIT_RPM
} = process.env;

const CONFIG = {
  chatModel: OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b",
  embedModel: "text-embedding-3-large",
  pineconeIndex: "forged-freedom-ai",
  maxQuestionLength: 2000,
  maxRPM: parseInt(RATE_LIMIT_RPM) || 60,
  topK: 30,
  maxQuotes: 12,
  isProd: NODE_ENV === "production"
};

/* =========================
   STARTUP VALIDATION
========================= */
if (!OPENROUTER_API_KEY) {
  console.error("❌ OPENROUTER_API_KEY required");
  process.exit(1);
}
if (!PINECONE_API_KEY) {
  console.error("❌ PINECONE_API_KEY required");
  process.exit(1);
}

/* =========================
   PINECONE CLIENT
========================= */
const pinecone = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pinecone.Index(CONFIG.pineconeIndex);

/* =========================
   EXPRESS APP
========================= */
const app = express();

app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(cors({
  origin: CONFIG.isProd ? ["https://forgedbyfreedom.com", "https://www.forgedbyfreedom.com"] : "*",
  methods: ["GET", "POST"],
  allowedHeaders: ["Content-Type", "Authorization"]
}));
app.use(express.json({ limit: "100kb" }));

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => console.log(`[${req.method}] ${req.path} ${res.statusCode} ${Date.now() - start}ms`));
  next();
});

// Rate limiting
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

setInterval(() => {
  const now = Date.now();
  for (const [ip, r] of rateLimit) if (now > r.reset + 60000) rateLimit.delete(ip);
}, 60000);

/* =========================
   OPENROUTER API
========================= */
async function callOpenRouter(endpoint, body, timeout = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`https://openrouter.ai/api/v1${endpoint}`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
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
  const data = await callOpenRouter("/embeddings", {
    model: CONFIG.embedModel,
    input: text
  });

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

/* =========================
   PINECONE SEARCH
========================= */
async function search(vector, namespace = "") {
  const query = { vector, topK: CONFIG.topK, includeMetadata: true };
  if (namespace) query.namespace = namespace;

  const result = await index.query(query);
  return result.matches || [];
}

/* =========================
   EVIDENCE EXTRACTION
========================= */
function extractQuotes(matches) {
  return matches
    .map(m => {
      const md = m.metadata || {};
      const text = md.text || md.chunk || md.content || md.transcript || "";
      if (!text.trim()) return null;

      return {
        text: text.trim(),
        channel: md.channel || extractChannelFromPath(md.source || md.file) || "unknown",
        speaker: md.speaker || "unknown",
        title: md.title || "unknown",
        source: md.source || md.file || "unknown",
        score: Math.round((m.score || 0) * 1000) / 1000
      };
    })
    .filter(Boolean)
    .slice(0, CONFIG.maxQuotes);
}

function extractChannelFromPath(path = "") {
  const match = path.match(/@[\w]+/);
  return match ? match[0] : null;
}

/* =========================
   SYNTHESIS PROMPT
========================= */
const SYSTEM_PROMPT = `You are Coach Bryan, an expert fitness and performance advisor with deep knowledge of training, nutrition, supplementation, peptides, hormones, and recovery protocols.

RESPONSE FORMAT:
1. First, paraphrase the user's question in your own words to confirm understanding
2. Then provide your answer based ONLY on the evidence provided
3. Be direct - no hedging, disclaimers, or "consult a doctor" deflections
4. Reference which expert the information comes from when citing claims
5. If sources disagree, acknowledge different perspectives
6. End with a brief, actionable takeaway

You have access to transcripts from respected experts in fitness, bodybuilding, sports medicine, and biohacking.`;

function buildUserPrompt(question, quotes) {
  const evidence = quotes
    .map((q, i) => `[${i + 1}] ${q.speaker !== "unknown" ? q.speaker : q.channel}: "${q.text}"`)
    .join("\n\n");

  return `Question: ${question}

EVIDENCE FROM EXPERT TRANSCRIPTS:
${evidence}

Remember: Paraphrase the question first, then answer using ONLY the evidence above.`;
}

/* =========================
   ENDPOINTS
========================= */
app.get("/health", (_req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

app.get("/status", async (_req, res) => {
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
  const startTime = Date.now();

  // Validation
  if (!question || typeof question !== "string") {
    return res.status(400).json({ error: "Question required", answer: null });
  }
  if (question.length > CONFIG.maxQuestionLength) {
    return res.status(400).json({ error: "Question too long", answer: null });
  }

  try {
    // 1. Embed question
    const vector = await embed(question.trim());

    // 2. Search Pinecone
    const matches = await search(vector, namespace);
    if (!matches.length) {
      return res.json({ answer: "No relevant evidence found.", sources: [] });
    }

    // 3. Extract quotes
    const quotes = extractQuotes(matches);
    if (!quotes.length) {
      return res.json({ answer: "No usable transcript text found.", sources: [] });
    }

    // 4a. Raw quotes mode
    if (mode === "quotes") {
      const answer = quotes
        .map((q, i) => `${i + 1}) "${q.text}"\n   — ${q.speaker !== "unknown" ? q.speaker : q.channel}`)
        .join("\n\n");

      return res.json({ answer, sources: quotes, mode: "quotes", timing: Date.now() - startTime });
    }

    // 4b. Synthesized mode (default)
    const messages = [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: buildUserPrompt(question, quotes) }
    ];

    const answer = await chat(messages);
    const attribution = [...new Set(quotes.map(q => q.channel))].filter(c => c !== "unknown");

    res.json({
      answer,
      sources: quotes,
      attribution,
      mode: "synthesized",
      timing: Date.now() - startTime
    });

  } catch (err) {
    console.error("[ASK ERROR]", err);
    res.status(500).json({
      error: CONFIG.isProd ? "Request failed" : err.message,
      answer: null
    });
  }
});

// 404
app.use((_req, res) => res.status(404).json({ error: "Not found" }));

// Error handler
app.use((err, _req, res, _next) => {
  console.error("[ERROR]", err);
  res.status(500).json({ error: "Internal server error" });
});

/* =========================
   GRACEFUL SHUTDOWN
========================= */
let server;
const shutdown = (sig) => {
  console.log(`\n[${sig}] Shutting down...`);
  server?.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10000);
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

/* =========================
   START
========================= */
const PORT_NUM = PORT || 5051;
server = app.listen(PORT_NUM, () => {
  console.log(`[FBF] Coach Bryan API :${PORT_NUM} (${CONFIG.isProd ? "prod" : "dev"})`);
  console.log(`[FBF] Model: ${CONFIG.chatModel}`);
});
