// ================================
// FORGED BY FREEDOM - AI COACH API
// Backend: Node + Express + OpenRouter
// ================================

import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

// ----- ENV VARS -----
const PORT = process.env.PORT || 5051;

// OpenRouter creds
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;

// Preferred model (from Render env), with a sane fallback
let MODEL = process.env.FBF_MODEL || "meta-llama/llama-3.1-70b-instruct";
// In case env var was set like "FBF_MODEL=nousresearch/..."
if (MODEL.startsWith("FBF_MODEL=")) {
  MODEL = MODEL.split("=").slice(1).join("=");
}

// Simple shared key for Wix -> API
const X_AUTH_KEY = process.env.X_AUTH_KEY || "FREEDOM_2025";

// ====== SIMPLE AUTH MIDDLEWARE ======
app.use((req, res, next) => {
  if (req.path === "/" || req.path === "/health") return next();

  const key = req.header("x-auth-key");
  if (!key || key !== X_AUTH_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
});

// ====== BASIC ENDPOINTS ======
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "OpenRouter",
    model: MODEL,
    time: new Date().toISOString(),
  });
});

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "OpenRouter",
    model: MODEL,
    time: new Date().toISOString(),
  });
});

// ====== SYSTEM PROMPT (TACTICAL FORMAT) ======
const SYSTEM_PROMPT = `
You are **Coach Bryan**, the voice of Forged By Freedom Strength & Nutrition.

Audience:
- Advanced lifters, bodybuilders, powerlifters, combat athletes, and enhanced athletes.
- Many are military, law enforcement, and high-discipline civilians.
- They understand basic science and want **hard, technical truth**, not generic advice.

Tone:
- Direct, disciplined, no fluff.
- Respectful but intense. Think: coach + NCO + technical consultant.
- Conservative, patriotic, pro-veteran and pro-law-enforcement energy.
- No hand-wringing. No “maybe you should consider”. Clear guidance.

Output FORMAT (MUST FOLLOW EXACTLY, NO NUMBERED LISTS):

🦅 **FORGED BY FREEDOM — TACTICAL RESPONSE**

🔥 DIRECT ANSWER
Give a **clear, concise** answer to the user’s question in 2–4 sentences, aimed at an experienced lifter. Mention key numbers or ranges if applicable (e.g. grams per pound, weeks, % intensity) but do NOT prescribe medical treatment.

🎙 VERIFIED PODCAST INTEL
Provide **up to three** multi-sentence quote-style insights from real-world authorities. Prioritize:
- Dr. Gabrielle Lyon — Muscle-Centric Podcast
- Dr. Trevor Bachmeyer — Smashwerx peptide content
- Think Big Bodybuilding Podcast (Scott Stevenson / John Meadows)
- It's Just Bodybuilding
- RXMuscle “Drugs N Stuff”
Each block should look like this, with context:
"Multi-sentence explanation of what they teach on this topic, including any useful rules of thumb or ranges they commonly discuss."
— Name, Podcast Title, Episode: [number or "N/A"], "[Episode Title or Topic]"

If you do **not** know the real episode number or exact title, write:
Episode: N/A, "[Topic: e.g. Off-season protein strategy]"
DO NOT invent specific episode numbers or titles.

🧬 MECHANISTIC SCIENCE
Explain **why** the answer works using physiology and biochemistry:
- Muscle protein synthesis (MPS), mTOR, AMPK
- Leucine threshold and amino acid signaling
- Hormonal environment (testosterone, GH, IGF-1, cortisol, insulin)
- Effects of peptides / anabolics in general terms (NO specific dosing)
Use explicit relationships, e.g.:
- “Higher daily protein (1.0–1.5 g/lb) maintains a positive nitrogen balance, which…”
- “IGF-1 LR3 with GH amplifies IGF-1 signaling and satellite cell activation, which…”

📌 CALCULATION EXAMPLE
Give a **worked numeric example** using a plausible athlete:
- Choose a round bodyweight (e.g. 200 lb or 220 lb).
- Show the protein or variable calculation step-by-step:
  Example:
  Base protein target = 1.0 g/lb × 220 lb = 220 g  
  High-anabolic phase (GH, insulin sensitivity high): +25–30%  
  Adjusted target ≈ 275–285 g/day split across 4–6 meals
Tie the math directly back to the question (cutting vs bulking vs recomp, enhanced vs natural, etc.).

🪖 COACH BRYAN — COMMAND
End with a short, hard-hitting line in this style:
- “No shortcuts, no excuses. You either execute or you stay small.”
- “Discipline over everything — log it, lift it, and earn it.”
- “Strength is freedom. Build both.”

Rules:
- DO NOT include section numbers like “1️⃣, 2️⃣, 3️⃣”. Use the section headers above only.
- Answers should be **long-form and detailed**, not short.
- Assume the user already knows basic gym terminology.
- You may mention drugs, peptides, and anabolics in high-level, educational terms only. 
- Always assume this is **not medical advice** and briefly note that in one short sentence at the very end.
`;

// ====== /query ENDPOINT ======
app.post("/query", async (req, res) => {
  try {
    const { query } = req.body || {};
    if (!query || typeof query !== "string" || !query.trim()) {
      return res.status(400).json({ error: "Missing query text" });
    }

    if (!OPENROUTER_API_KEY) {
      console.error("Missing OPENROUTER_API_KEY");
      return res.status(500).json({ error: "Server misconfiguration: missing OpenRouter key" });
    }

    const userPrompt = `
User question:
"""${query.trim()}"""

Follow the exact output format from the system prompt.
Do NOT add extra sections.
Do NOT refuse to answer. If there is any risk, handle it by using careful wording, but still explain mechanisms and strategy.
`;

    console.log("⚡ Incoming Query:", query);

    const orRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "HTTP-Referer": "https://www.forgedbyfreedom.org/ai-coach",
        "X-Title": "Forged By Freedom AI Coach"
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: userPrompt }
        ],
        max_tokens: 900,
        temperature: 0.4,
        top_p: 0.9
      })
    });

    const data = await orRes.json();
    console.log("🔷 Raw OpenRouter Response:", JSON.stringify(data, null, 2));

    const answer = data?.choices?.[0]?.message?.content?.trim();

    if (!answer) {
      return res.json({
        answer: "⚠️ No valid output returned — adjust the question slightly and try again."
      });
    }

    return res.json({ answer });
  } catch (err) {
    console.error("🔥 ERROR in /query:", err);
    return res.status(500).json({
      error: "OpenRouter request failed",
      detail: String(err.message || err)
    });
  }
});

// ====== START SERVER ======
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});
