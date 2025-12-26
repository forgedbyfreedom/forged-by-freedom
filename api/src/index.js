// src/index.js
import express from "express";
import cors from "cors";
import helmet from "helmet";
import dotenv from "dotenv";
import { formatAnswer } from "./fbfAnswer.js";

dotenv.config();
const app = express();
app.use(express.json());
app.use(cors());
app.use(helmet());

const AUTH_KEY = process.env.X_AUTH_KEY || "FREEDOM_2025";

// security check middleware
app.use((req, res, next) => {
  const key = req.headers["x-auth-key"];
  if (!key || key !== AUTH_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
});

// ------- HEALTH ENDPOINT -------
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "ForgedByFreedom API",
    timestamp: new Date().toISOString(),
  });
});

// ------- QUERY ENDPOINT -------
app.post("/query", async (req, res) => {
  const { query } = req.body;

  // TEMPORARY MOCK ANSWER until DB + podcast engine is active
  const mock = formatAnswer({
    question: query,
    podcastQuotes: [
      {
        quote: "Muscle is earned by progressive overload and recovery tracking.",
        show: "Think Big Bodybuilding Podcast",
        episode: "Overtraining Truth",
        speaker: "Scott Stevenson"
      }
    ],
    medical:
      "Training response is dictated by endocrine balance (testosterone/cortisol), nervous system fatigue, and nutrient partitioning (insulin + GH/IGF-1 axis).",
    coach: "No excuses. Discipline over everything."
  });

  res.json(mock);
});

// ------- START SERVER -------
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🔥 ForgedByFreedom API live on port ${PORT}`);
});

