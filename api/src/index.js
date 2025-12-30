import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(express.json());
app.use(cors());

const PORT = process.env.PORT || 5051;

// OpenRouter Key
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;

// Model – fast + cost-efficient
const MODEL = process.env.FBF_MODEL || "meta-llama/llama-3.1-70b-instruct";

// SYSTEM TONE — Pro-American, military, law enforcement culture
const SYSTEM_PROMPT = `
You respond as a conservative American bodybuilding, powerlifting, peptide coach — 
pro-military, pro-law enforcement, disciplined, no-nonsense. 
Give facts. Avoid opinions. Straight tactical guidance.
`;

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "OpenRouter",
    model: MODEL,
    time: new Date().toISOString(),
  });
});

// Main query endpoint
app.post("/query", async (req, res) => {
  console.log("⚡ Incoming Query:", req.body.query);
  const query = req.body.query || "";

  try {
    const aiRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://www.forgedbyfreedom.org/",
        "X-Title": "Forged By Freedom Coach AI"
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: query }
        ]
      })
    });

    const data = await aiRes.json();
    console.log("🔷 Raw OpenRouter Response:", data);

    const aiText =
      data?.choices?.[0]?.message?.content ||
      data?.choices?.[0]?.message?.text ||
      data?.choices?.[0]?.text ||
      "⚠️ No response generated.";

    return res.json({ answer: aiText });

  } catch (err) {
    console.error("❌ API ERROR:", err);
    return res.status(500).json({ error: "Server error — see logs" });
  }
});

app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});
