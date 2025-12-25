// src/index.js (ESM version)
import express from "express";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// 🔐 AUTH MIDDLEWARE
app.use((req, res, next) => {
  const key = req.headers["x-auth-key"];
  if (!key || key !== process.env.AUTH_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
});

// Health route
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "ForgedByFreedom API",
    timestamp: new Date().toISOString(),
  });
});

app.listen(PORT, () => {
  console.log(`🔥 ForgedByFreedom API live on port ${PORT}`);
});

