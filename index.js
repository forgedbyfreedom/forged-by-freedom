import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import { Pinecone } from "@pinecone-database/pinecone";

// ========== ENV ==========
const {
  OPENROUTER_API_KEY,
  PINECONE_API_KEY,
  PORT
} = process.env;

const EMBED_MODEL = "text-embedding-3-large";
const INDEX_NAME = "forged-freedom-ai";

// ========== PINECONE ==========
const pc = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pc.Index(INDEX_NAME);

// ========== EXPRESS ==========
const app = express();
app.use(cors());
app.use(bodyParser.json());

// ========== HEALTH ==========
app.get("/status", async (req, res) => {
  try {
    const stats = await index.describeIndexStats();
    res.json({
      status: "ok",
      pinecone: true,
      index: INDEX_NAME,
      namespaces: Object.keys(stats.namespaces || {}),
      time: new Date().toISOString()
    });
  } catch (err) {
    res.json({ status: "error", error: err.message });
  }
});

// ========== HELPERS ==========
function normalize(text = "") {
  return text.toLowerCase();
}

function matchesAllAnchors(text, anchors) {
  const t = normalize(text);
  return anchors.every(a => t.includes(a));
}

// ========== ASK COACH BRYAN ==========
app.post("/ask", async (req, res) => {
  const { question } = req.body;
  if (!question) {
    return res.json({ answer: "No question provided." });
  }

  try {
    // ---------- 1. Embed query ----------
    const embedResp = await fetch("https://api.openai.com/v1/embeddings", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: EMBED_MODEL,
        input: question
      })
    });

    const embedData = await embedResp.json();
    const queryVector = embedData.data[0].embedding;

    // ---------- 2. Namespaces ----------
    const namespaces = [
      "",
      "default",
      "transcripts",
      "thinkbig_priority",
      "anabolic_bodybuilding_priority",
      "women_steroids"
    ];

    // ---------- 3. Anchors (RELEVANCE, NOT SCORING) ----------
    const q = normalize(question);

    const requiredAnchors = [];
    if (q.includes("tren")) requiredAnchors.push("tren");
    if (q.includes("women") || q.includes("female")) requiredAnchors.push("women");
    if (q.includes("viril")) {
      requiredAnchors.push("viril");
    }

    // ---------- 4. Query Pinecone ----------
    let matches = [];
    for (const ns of namespaces) {
      const result = await index.query({
        vector: queryVector,
        topK: 12,
        includeMetadata: true,
        namespace: ns || undefined
      });

      matches.push(...(result.matches || []));
    }

    // ---------- 5. FILTER by relevance ----------
    const relevant = matches.filter(m => {
      const text = m.metadata?.text || "";
      return matchesAllAnchors(text, requiredAnchors);
    });

    if (relevant.length === 0) {
      return res.json({
        answer: "No verbatim transcript quotes directly addressing this question were found.",
        sources: []
      });
    }

    // ---------- 6. Select top quotes ----------
    const top = relevant.slice(0, 3).map((m, i) => ({
      id: i + 1,
      quote: m.metadata.text,
      speaker: m.metadata.speaker || "Unknown Speaker",
      podcast: m.metadata.podcast || "Unknown Podcast",
      source: m.metadata.source || "Transcript"
    }));

    // ---------- 7. Respond ----------
    res.json({
      answer: top.map(q => `${q.id}) "${q.quote}" — ${q.speaker}, ${q.podcast}`).join("\n\n"),
      sources: top
    });

  } catch (err) {
    res.json({
      answer: "Server error while querying Ask Coach Bryan.",
      error: err.message
    });
  }
});

// ========== START ==========
const SERVER_PORT = PORT || 5051;
app.listen(SERVER_PORT, () => {
  console.log(`[FBF] Ask Coach Bryan running on :${SERVER_PORT}`);
});
