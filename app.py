#!/usr/bin/env python3
"""
app.py — Forged by Freedom AI Coach API (Clean)
- Pinecone semantic search
- OpenRouter embeddings + chat completions
- Stats endpoint for Wix header
"""

import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-2-pro").strip()
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large").strip()

# Where stats.json lives in your repo/deploy
STATS_PATH = os.getenv("STATS_PATH", "stats.json").strip()

if not PINECONE_API_KEY or not OPENROUTER_API_KEY:
    raise ValueError("Missing required API keys (PINECONE_API_KEY / OPENROUTER_API_KEY).")

# ---- Pinecone init (v8+ SDK style) ----
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
available = [idx["name"] for idx in pc.list_indexes()]
if PINECONE_INDEX_NAME not in available:
    raise ValueError(f"Index '{PINECONE_INDEX_NAME}' not found. Available: {available}")
index = pc.Index(PINECONE_INDEX_NAME)

app = Flask(__name__)

# Restrict CORS to your site(s) — add your Wix domain(s) here
allowed_origins = [
    "https://www.forgedbyfreedom.org",
    "https://forgedbyfreedom.org",
    "http://localhost:3000",
    "http://localhost:5173",
]
CORS(app, resources={r"/*": {"origins": allowed_origins}})

def _now():
    return datetime.utcnow().isoformat() + "Z"

@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "service": "Forged by Freedom AI Coach API",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "time": _now(),
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "time": _now()})

@app.route("/version")
def version():
    return jsonify({
        "version": "fbf-api-2025-12-20",
        "time": _now(),
    })

@app.route("/stats")
def stats():
    """
    Returns stats.json if present.
    Your Wix header expects:
      data.summary.channels
      data.summary.episodes
      data.summary.total_words
      data.channels (optional list)
    """
    try:
        if not os.path.exists(STATS_PATH):
            return jsonify({
                "summary": {"channels": 0, "episodes": 0, "total_words": 0},
                "channels": [],
                "warning": f"{STATS_PATH} not found on server",
                "time": _now(),
            }), 200

        with open(STATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["time"] = _now()
        return jsonify(data), 200

    except Exception as e:
        return jsonify({"error": f"stats failed: {e}", "time": _now()}), 500

@app.route("/search", methods=["POST"])
def search():
    """
    Expected payload: { "query": "...", "top_k": 5 }
    Returns: { response, sources, timestamp }
    """
    try:
        data = request.get_json(force=True) or {}
        query = (data.get("query") or "").strip()
        top_k = int(data.get("top_k", 5))

        if not query:
            return jsonify({"error": "Missing query"}), 400

        # 1) Embed with OpenRouter
        emb = requests.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": EMBED_MODEL, "input": query},
            timeout=45,
        )
        if emb.status_code >= 400:
            return jsonify({
                "error": "Embedding request failed",
                "status": emb.status_code,
                "detail": emb.text[:400],
            }), 502

        query_vector = emb.json()["data"][0]["embedding"]

        # 2) Pinecone query
        results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
        matches = results.get("matches") or []
        if not matches:
            return jsonify({
                "query": query,
                "response": "No relevant results found in the transcript database.",
                "sources": [],
                "timestamp": _now(),
            }), 200

        # 3) Build context + sources
        context_chunks = []
        sources = []
        for m in matches:
            md = (m or {}).get("metadata") or {}
            txt = (md.get("text") or "")[:1200]
            if txt:
                context_chunks.append(txt)
            sources.append(md.get("source") or md.get("title") or "Unknown")

        context = "\n\n".join(context_chunks)

        # 4) Chat completion
        chat = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are the Forged By Freedom AI Coach. "
                            "Be concise, science-based, practical, and motivational. "
                            "Use the provided transcript context. "
                            "If context is insufficient, say so and give best-practice guidance."
                        ),
                    },
                    {"role": "user", "content": f"Question: {query}\n\nContext:\n{context}"}
                ],
                "temperature": 0.4,
            },
            timeout=75,
        )
        if chat.status_code >= 400:
            return jsonify({
                "error": "Chat completion failed",
                "status": chat.status_code,
                "detail": chat.text[:400],
            }), 502

        answer = chat.json()["choices"][0]["message"]["content"]

        return jsonify({
            "query": query,
            "response": answer,
            "sources": sources[:top_k],
            "timestamp": _now(),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e), "timestamp": _now()}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=True)
