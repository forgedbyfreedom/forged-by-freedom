// ================================
// FORGED BY FREEDOM - AI COACH API
// ================================

import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());
app.use(express.json());

// -------- ENVIRONMENT VARIABLES (Render Dashboard → Environment) --------
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const MODEL = process.env.FBF_MODEL || "gpt-4o-mini";
const PORT = process.env.PORT || 3000;

// ------------------- BASIC CHECK ENDPOINTS -------------------
app.get("/", (req, res) => {
  res.send("🔥 Forged By Freedom API Online");
});

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    model: MODEL,
    time: new Date().toISOString(),
  });
});

// ------------------- MAIN QUERY ROUTE -------------------
app.post("/query", async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) return res.status(400).json({ error: "Missing query parameter" });

    console.log("⚡ Incoming Query:", query);

    const openaiRes = await fetch(
      "https://api.openai.com/v1/chat/completions",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: MODEL,
          messages: [
            {
              role: "system",
              content:
                "You are Coach Bryan, a disciplined bodybuilding and powerlifting coach. Answer directly, no filler.",
            },
            { role: "user", content: query },
          ],
          max_tokens: 500,
        }),
      }
    );

    const data = await openaiRes.json();

    console.log("🔷 OpenAI Raw Response:", data);

    const answer =
      data?.choices?.[0]?.message?.content ||
      "No response generated.";

    return res.json({ answer });
  } catch (err) {
    console.error("🔥 ERROR in /query:", err);
    res.status(500).json({ error: err.message });
  }
});

// ------------------- START SERVER -------------------
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});
