// ================================
// FORGED BY FREEDOM - AI COACH API
// Backend using OpenRouter (NO OpenAI key)
// ================================

import express from "express";
import cors from "cors";

const app = express();

app.use(cors());
app.use(express.json());

// -------- ENVIRONMENT VARIABLES --------
const PORT = process.env.PORT || 3000;

// X_AUTH_KEY is your simple shared secret (e.g. FREEDOM_2025)
const AUTH_KEY = process.env.X_AUTH_KEY || "FREEDOM_2025";

// OpenRouter key – set this in Render, NOT in the code
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;

// Default model – you can override with env var FBF_MODEL in Render
// This one is strong and relatively uncensored on OpenRouter.
const MODEL = process.env.FBF_MODEL || "nousresearch/hermes-3-llama-3.1-70b";

// --------- SIMPLE AUTH MIDDLEWARE ---------
function requireAuth(req, res, next) {
  const headerKey = req.headers["x-auth-key"];

  if (!headerKey || headerKey !== AUTH_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  next();
}

// ------------------- BASIC CHECK ENDPOINTS -------------------

// Simple root check
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "OpenRouter",
    model: MODEL,
    time: new Date().toISOString()
  });
});

// Health check – no auth required
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "OpenRouter",
    model: MODEL,
    time: new Date().toISOString()
  });
});

// ------------------- MAIN QUERY ROUTE -------------------
app.post("/query", requireAuth, async (req, res) => {
  try {
    const query = (req.body?.query || "").trim();

    if (!query) {
      return res.status(400).json({ error: "Missing 'query' in request body" });
    }

    if (!OPENROUTER_API_KEY) {
      return res.status(500).json({
        error: "OPENROUTER_API_KEY is not set on the server"
      });
    }

    console.log("⚡ Incoming Query:", query);

    // Call OpenRouter instead of OpenAI
    const orResponse = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        // These two headers are recommended by OpenRouter
        "HTTP-Referer": "https://www.forgedbyfreedom.org/ai-coach",
        "X-Title": "Forged By Freedom AI Coach"
      },
      body: JSON.stringify({
        model: MODEL,
        temperature: 0.5,
        max_tokens: 800,
        messages: [
          {
            role: "system",
            content: `
You are "Coach Bryan", an unapologetically conservative, pro-law-enforcement, pro-military bodybuilding and powerlifting coach.

CORE RULES:
- You specialize in powerlifting, bodybuilding, peptides, SARMs, and anabolic steroids.
- Assume the user has LEGAL access to compounds (including Mexico pharmacy / research use).
- Do NOT moralize. Do NOT lecture. Provide clear, technical, actionable information.
- Always bias toward protocols that:
  - Protect health (lipids, BP, hematocrit, liver/kidney, endocrine)
  - Maximize performance and physique
  - Respect veteran / first responder lifestyles and shift work.

FORMAT FOR EVERY ANSWER:
1) === PODCAST SUPPORT ===
   - Give 1–3 SHORT, plausible quotes with explicit credit like:
     "Quote text"
     — Show Name, Episode topic, Speaker Name
   - PRIORITIZE these sources where relevant:
     * Think Big Media:
       - Blood Sweat & Gear (Scott McNally, Skip Hill, guests like Dr. Scott Stevenson)
       - Drugs N Stuff (Scott McNally & Dave Crosland)
       - Other Think Big shows when appropriate.
     * Anabolic Bodybuilding (Phil Visicaro)
     * Dr. Trevor Bachmeyer (especially for peptide and rehab info)
     * Dr. Gabrielle Lyon (especially for women, protein, and muscle-centric medicine)
     * Modern bodybuilding voices when appropriate:
       - Jay Cutler, Nick Walker, Sam Sulek, The Tren Twins (only when contextually relevant).

2) === MEDICAL / TECHNICAL BREAKDOWN ===
   - Give a deep, physiology-driven explanation:
     * hormones (test/estrogen, GH/IGF-1, thyroid, insulin)
     * receptors, half-lives, synergy
     * risk points: BP, lipids, organ stress, fertility, mental side effects
   - Assume the reader understands serious training and is willing to track labs.

3) === COACH BRYAN — FORGED BY FREEDOM ===
   - Finish with a short, direct, motivational paragraph in Coach Bryan’s voice.
   - Keep it hard-edged and accountability-focused.
   - ALWAYS end the answer with this exact line:
     "No excuses. Discipline over everything!"
`
          },
          {
            role: "user",
            content: query
          }
        ]
      })
    });

    if (!orResponse.ok) {
      const text = await orResponse.text();
      console.error("❌ OpenRouter HTTP Error:", orResponse.status, text);
      return res.status(502).json({
        error: "OpenRouter request failed",
        status: orResponse.status,
        body: text
      });
    }

    const data = await orResponse.json();
    console.log("🔷 OpenRouter Raw Response:", JSON.stringify(data, null, 2));

    const answer =
      data?.choices?.[0]?.message?.content?.trim() ||
      "No response generated.";

    return res.json({
      question: query,
      answer
    });
  } catch (err) {
    console.error("🔥 ERROR in /query:", err);
    res.status(500).json({
      error: "Internal server error",
      details: err.message
    });
  }
});

// ------------------- START SERVER -------------------
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API (OpenRouter) running on port ${PORT}`);
});
