/**  Forged By Freedom – API Server  **/
import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 5051;
const MODEL = process.env.FBF_MODEL || "nousresearch/hermes-3-llama-3.1-70b";
const API_KEY = process.env.OPENROUTER_API_KEY;

/* ===============================
   SYSTEM MESSAGE FOR PERFECT OUTPUT
================================ */
const SYSTEM_MESSAGE = `
You are FBF – Forged By Freedom AI Coach.
Tone: direct, tactical, pro–law enforcement, pro–military, pro–America.
Audience: competitive lifters, jiu-jitsu athletes, veterans.

REQUIRED ANSWER FORMAT:
1️⃣ Open with a concise tactical answer (2–4 sentences)
2️⃣ Provide 3 SOURCE QUOTES from:
   – Dr. Gabriel Lyon ("The Muscle-Centric Podcast")
   – Dr. Trevor Bachmeyer ("Smashwerx" peptide content)
   – Think Big Bodybuilding podcast
   – Anabolic Bodybuilding
   Include:
     • speaker name
     • episode or title (if available)
     • timestamp OR topic reference
     • direct quote inside quotation marks
3️⃣ Provide SCIENTIFIC EXPLANATION citing physiology, peptides, hormones, anabolic pathways
4️⃣ Close with a Coach Bryan Motivation line, format:
   💪 "— Coach Bryan: {1 tactical statement}"
`;

/* ===============================
   FUNCTION – Send request to OpenRouter
================================ */
async function aiAnswer(userPrompt) {
  const prompt = `User Question: ${userPrompt}\n\nFollow required FBF Output Rules.`

  const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
      "HTTP-Referer": "https://forgedbyfreedom.org",
      "X-Title": "ForgedByFreedom AI"
    },
    body: JSON.stringify({
      model: MODEL,
      messages: [
        { role: "system", content: SYSTEM_MESSAGE },
        { role: "user", content: userPrompt }
      ]
    })
  });

  const data = await res.json();
  console.log("🔷 Raw OpenRouter Response:", data);

  try {
    return data.choices?.[0]?.message?.content || "⚠️ No output returned — adjust prompt.";
  } catch {
    return "⚠️ AI response unreadable — retry query.";
  }
}

/* ===============================
   ENDPOINTS
================================ */

// GET browser test
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    backend: "OpenRouter",
    model: MODEL,
    time: new Date().toISOString()
  });
});

// GET debug-test — test AI using browser
app.get("/debug-test", async (req, res) => {
  const q = req.query.query || "no query";
  const answer = await aiAnswer(q);
  res.json({ question: q, answer });
});

// POST – main request Wix uses
app.post("/query", async (req, res) => {
  const { query } = req.body || {};
  if (!query) return res.status(400).json({ error: "Missing query" });

  const answer = await aiAnswer(query);
  res.json({ answer });
});

/* =============================== */

app.listen(PORT, () =>
  console.log(`🔥 FBF API running on port ${PORT}`)
);
