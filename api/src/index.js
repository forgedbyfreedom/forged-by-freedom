// ================================
// FORGED BY FREEDOM - AI BACKEND
// ================================

import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

// ------------ ENVIRONMENT VARIABLES (SET IN RENDER) ------------
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const MODEL = process.env.FBF_MODEL || "meta-llama/llama-3.1-70b-instruct";
const PORT = process.env.PORT || 3000;
const AUTH_KEY = process.env.X_AUTH_KEY || "FREEDOM_2025";

// ------------ AUTH MIDDLEWARE ------------
function verifyAuth(req, res, next) {
  const headerKey = req.headers["x-auth-key"];
  if (!headerKey || headerKey !== AUTH_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
}

// ------------ BASIC HEALTH ROUTES ------------
app.get("/", (req, res) => {
  res.send("🔥 Forged By Freedom API Online");
});

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    model: MODEL,
    time: new Date().toISOString()
  });
});

// ------------ MAIN AI QUERY ROUTE ------------
app.post("/query", verifyAuth, async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) return res.status(400).json({ error: "Missing query" });

    console.log("⚡ Incoming Query:", query);

    const openRouterRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          {
            role: "system",
            content: `
You are COACH BRYAN — military mindset, police, discipline-first bodybuilding coach. 
Answer FAST, direct, **no filler**, no disclaimers. 
Context allowed: peptides, steroids (legal in MX), GH, cycles, Retatrutide, Tren, RAD-140, BJJ conditioning, powerlifting, nutrition.
Never say “consult a doctor”.
          `
          },
          { role: "user", content: query }
        ],
        max_tokens: 500
      })
    });

    const data = await openRouterRes.json();

    console.log("🔷 Raw OpenRouter Response:", data);

    const answer = data?.choices?.[0]?.message?.content || "⚠️ No response generated.";
    return res.json({ answer });

  } catch (err) {
    console.error("🔥 ERROR:", err);
    res.status(500).json({
      error: "Server Error",
      details: err.message
    });
  }
});

// ------------ LAUNCH SERVER ------------
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API (OpenRouter) running on port ${PORT}`);
});
