// -----------------------------
// FBF API – Final Clean Version
// -----------------------------
import express from "express";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;
const AUTH_KEY = process.env.FBF_API_KEY || "FREEDOM_2025";

// -----------------------------
// Middleware
// -----------------------------
app.use(cors());
app.use(express.json({ limit: "5mb" }));

// Auth – allow /health to be public
app.use((req, res, next) => {
  if (req.path === "/health") return next();
  const key = req.header("x-auth-key");
  if (!key || key !== AUTH_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
});

// -----------------------------
// Health Check
// -----------------------------
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "ForgedByFreedom API",
    timestamp: new Date().toISOString()
  });
});

// -----------------------------
// Answer Builder – formatting logic
// -----------------------------
function buildPodcastSection(matches = []) {
  const top = matches.filter(m => m.quote && m.podcastTitle).slice(0, 3);
  if (!top.length) {
    return `No direct podcast quotes found — pulling answer from transcripts & medical files.`;
  }
  return top
    .map(m => {
      const ep = m.episodeTitle || m.episodeSubject || "Unknown Episode";
      const sp = m.speaker || "Unknown Speaker";
      return `"${m.quote.trim()}"
— ${m.podcastTitle.trim()}, Episode: ${ep.trim()}, Speaker: ${sp.trim()}`;
    })
    .join("\n\n");
}

function buildTechnicalSection(text) {
  return text?.trim()
    ? text.trim()
    : `Technical breakdown unavailable — (medical LLM wiring pending).`;
}

function buildCoachCloser() {
  return `
You already know what half measures got you — pain, regret, wasted time.
Run the plan, track the data, and execute without negotiation.

No one is coming. YOU are the response force.

— Coach Bryan, Forged by Freedom Strength & Nutrition
  `.trim();
}

function buildFullAnswer(question) {
  const fakeMatches = [
    {
      quote: "Muscle is earned by progressive overload and recovery tracking.",
      podcastTitle: "Think Big Bodybuilding Podcast",
      episodeTitle: "Overtraining Truth",
      speaker: "Scott Stevenson"
    }
  ];

  const technical = `
Training response = endocrine balance (T/cortisol), nervous system fatigue (HRV/sleep),
and nutrient partitioning (insulin sensitivity + GH/IGF-1 axis). Misalignment = no results.
  `.trim();

  return {
    question,
    answer: [
      "=== PODCAST SUPPORT ===",
      buildPodcastSection(fakeMatches),
      "",
      "=== TECHNICAL BREAKDOWN ===",
      buildTechnicalSection(technical),
      "",
      "=== COACH BRYAN ===",
      buildCoachCloser()
    ].join("\n")
  };
}

// -----------------------------
// Main Query Route
// -----------------------------
app.post("/query", async (req, res) => {
  try {
    const question = (req.body?.query || "").trim();
    if (!question) return res.status(400).json({ error: "Missing 'query' in request body" });

    const output = buildFullAnswer(question);
    return res.json(output);
  } catch (err) {
    console.error("❌ Query Error:", err);
    res.status(500).json({ error: "Server failure" });
  }
});

// -----------------------------
// Start Server
// -----------------------------
app.listen(PORT, () => {
  console.log(`🔥 ForgedByFreedom API live on port ${PORT}`);
});

