/**
 * Forged by Freedom API – Ask Coach Bryan (Node)
 *
 * Responsibilities:
 * - Accept /ask requests
 * - Call Python retrieval engine (JSON mode)
 * - Render STRICT quote-only answers
 * - NEVER show unrelated sources
 * - HONEST empty-state behavior
 */

import express from "express";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";

const app = express();
app.use(express.json());

// -------------------------------
// CONFIG
// -------------------------------

const PORT = process.env.PORT || 3000;
const AUTH_KEY = process.env.X_AUTH_KEY;

// IMPORTANT: adjust only if your repo layout differs
const PYTHON_ENGINE = path.resolve(
  process.cwd(),
  "ingest/run_openrouter_answer.py"
);

// -------------------------------
// AUTH MIDDLEWARE (optional)
// -------------------------------

function auth(req, res, next) {
  const key = req.headers["x-auth-key"];
  if (!AUTH_KEY || key === AUTH_KEY) return next();
  return res.status(401).json({ error: "Unauthorized" });
}

// -------------------------------
// FORMATTER (CRITICAL FIX)
// -------------------------------

function formatQuoteOnlyAnswer(payload) {
  if (!payload || payload.ok !== true) {
    return (
      "Answer:\n" +
      "An error occurred while generating this response.\n\n" +
      "Sources:\n(none)"
    );
  }

  const quotes = payload.quotes || [];

  // ✅ HARD EMPTY STATE — NO SOURCES
  if (quotes.length === 0) {
    const note =
      payload.note ||
      "No verbatim transcript excerpts were found that explicitly address this question.";

    return (
      "Answer:\n" +
      note +
      "\n\n" +
      "Sources:\n(none)"
    );
  }

  // ✅ NORMAL QUOTE-ONLY OUTPUT
  let out = "Answer:\n";

  quotes.forEach((q, i) => {
    const text = q.text?.trim() || "";
    const speaker = q.speaker || "Unknown Speaker";
    const podcast = q.podcast || "Unknown Podcast";
    out += `${i + 1}) "${text}" — ${speaker}, ${podcast}\n`;
  });

  out += "\nSources:\n";

  quotes.forEach((q) => {
    out += `- Podcast: ${q.podcast || "Unknown Podcast"}\n`;
    out += `  Episode: ${q.episode || "Unknown Episode"}\n`;
    out += `  Speaker: ${q.speaker || "Unknown Speaker"}\n`;
    if (q.timestamp) out += `  Timestamp: ${q.timestamp}\n`;
    if (q.source) out += `  Source: ${q.source}\n`;
    out += `  Quote: "${q.text.trim()}"\n\n`;
  });

  return out.trim();
}

// -------------------------------
// /ask ENDPOINT
// -------------------------------

app.post("/ask", auth, async (req, res) => {
  const question = (req.body?.question || "").trim();

  if (!question) {
    return res.status(400).json({
      answer: "Answer:\nNo question provided.\n\nSources:\n(none)",
    });
  }

  // Spawn Python engine
  const py = spawn("python3", [PYTHON_ENGINE]);

  let stdout = "";
  let stderr = "";

  py.stdout.on("data", (data) => {
    stdout += data.toString();
  });

  py.stderr.on("data", (data) => {
    stderr += data.toString();
  });

  py.on("close", (code) => {
    if (code !== 0 || !stdout) {
      console.error("Python engine error:", stderr);
      return res.status(500).json({
        answer:
          "Answer:\n" +
          "An internal engine error occurred.\n\n" +
          "Sources:\n(none)",
      });
    }

    let payload;
    try {
      payload = JSON.parse(stdout);
    } catch (e) {
      console.error("JSON parse error:", stdout);
      return res.status(500).json({
        answer:
          "Answer:\n" +
          "Response parsing error.\n\n" +
          "Sources:\n(none)",
      });
    }

    const answerText = formatQuoteOnlyAnswer(payload);
    return res.json({ answer: answerText });
  });

  // Send JSON input to Python
  py.stdin.write(JSON.stringify({ question }));
  py.stdin.end();
});

// -------------------------------
// HEALTH CHECK
// -------------------------------

app.get("/", (_, res) => {
  res.json({ status: "Forged by Freedom API online" });
});

// -------------------------------
// START SERVER
// -------------------------------

app.listen(PORT, () => {
  console.log(`🔥 Forged by Freedom API running on port ${PORT}`);
});
