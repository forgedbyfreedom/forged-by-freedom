import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
const PORT = process.env.PORT || 5051;

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY;  // stored in Render > Environment
const MODEL = process.env.FBF_MODEL || "nousresearch/hermes-3-llama-3.1-70b";

app.use(cors());
app.use(express.json());

// ------------------ HOME TEST ENDPOINT ------------------
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    service: "Forged By Freedom API",
    backend: "OpenRouter",
    model: MODEL,
    time: new Date().toISOString()
  });
});

// ------------------ QUERY ENDPOINT ----------------------
app.post("/query", async (req, res) => {
  try {
    const { question } = req.body;
    if (!question) return res.json({ answer: "No question provided." });

    const system_prompt = `
You respond as COACH BRYAN – Conservative, pro-military, pro-law enforcement.
You ALWAYS answer using this structure:

🦅 FORGED BY FREEDOM — TACTICAL RESPONSE

🔥 DIRECT ANSWER
Give the fast first answer.

🎙 VERIFIED PODCAST SOURCE QUOTES (minimum 3)
You **must pull**:
– Think Big Bodybuilding (Scott Stevenson, John Meadows)
– Muscle-Centric Podcast (Gabrielle Lyon)
– Smashwerx peptides (Dr. Trevor Bachmeyer)
– Drugs n Stuff – Enhanced bodybuilding
Provide:
• Speaker name
• Podcast title
• Episode number if known
• DIRECT quote — minimum 2 sentences
• What the quote means (1 sentence)

🧬 SCIENCE — ADVANCED EXPLANATION
Use medical physiology:
– nitrogen balance
– mTOR
– androgen receptor binding
– GH/IGF-1 protein turnover
– dose ranges
– calculation formulas

📌 CALCULATION EXAMPLE
Show math in grams, lbs, mg, IU, etc.

🪖 COACH BRYAN — COMMAND
End with a motivational line in character.
`;

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [
          { role: "system", content: system_prompt },
          { role: "user", content: question }
        ],
        max_tokens: 1500,
        temperature: 0.6
      })
    });

    const data = await response.json();
    console.log("🔷 RAW MODEL OUTPUT:", JSON.stringify(data, null, 2));

    const content =
      data?.choices?.[0]?.message?.content ||
      "⚠️ Model returned no valid output.";

    return res.json({ answer: content });

  } catch (err) {
    console.error("❌ ERROR:", err);
    res.status(500).json({ error: "Server Error" });
  }
});

// ------------------ START SERVER ------------------------
app.listen(PORT, () => {
  console.log(`🔥 Forged By Freedom API running on port ${PORT}`);
});
