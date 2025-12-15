#!/usr/bin/env python3
"""
app.py — Forged by Freedom Search + AI Engine
──────────────────────────────────────────────
Connects:
    🧠 Pinecone vector database
    🤖 OpenRouter (Nous Hermes 2 Pro or other model)
    🌐 Flask API server

Endpoints:
    ✅ /api/search — AI semantic search + response
    ✅ /health — Health check
"""

from flask import Flask, request, jsonify
from pinecone import Pinecone
from dotenv import load_dotenv
import requests
import os
from datetime import datetime

# ============================================================
# 🧩 Load environment
# ============================================================
load_dotenv()
print("✅  Loaded environment — Index:", os.getenv("PINECONE_INDEX_NAME", "not set"))

# ============================================================
# 🔐 Environment variables
# ============================================================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-2-pro")
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")

if not PINECONE_API_KEY:
    raise ValueError("❌ Missing Pinecone API key (PINECONE_API_KEY). Check .env file.")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ Missing OpenRouter API key (OPENROUTER_API_KEY). Check .env file.")

# ============================================================
# 🔌 Initialize Pinecone
# ============================================================
from pinecone import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
PINECONE_PROJECT = os.getenv("PINECONE_PROJECT", "default")

if not PINECONE_API_KEY:
    raise ValueError("❌ Missing Pinecone API key (PINECONE_API_KEY). Check .env or GitHub secrets.")

print(f"✅  Loaded environment — Index: {PINECONE_INDEX_NAME} | Env: {PINECONE_ENVIRONMENT} | Project: {PINECONE_PROJECT}")

try:
    pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
    index = pc.Index(PINECONE_INDEX_NAME)
except Exception as e:
    raise RuntimeError(f"❌ Pinecone connection failed: {e}")

# ============================================================
# ⚙️ Flask app
# ============================================================
app = Flask(__name__)

@app.route("/api/search", methods=["POST"])
def api_search():
    """Perform semantic search and generate AI response."""
    try:
        data = request.json or {}
        query = data.get("query", "").strip()
        top_k = int(data.get("top_k", 5))

        if not query:
            return jsonify({"error": "Missing query"}), 400

        # 1️⃣ Create embedding using OpenRouter
        embed_url = f"{OPENROUTER_BASE_URL}/embeddings"
        embed_payload = {"model": EMBED_MODEL, "input": query}

        embed_resp = requests.post(
            embed_url,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json=embed_payload,
            timeout=30,
        )
        embed_resp.raise_for_status()
        query_vector = embed_resp.json()["data"][0]["embedding"]

        # 2️⃣ Query Pinecone
        results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
        matches = results.get("matches", [])

        if not matches:
            return jsonify({"response": "No results found."}), 200

        # 3️⃣ Combine context
        context = "\n\n".join([
            m["metadata"].get("text", "")[:1500]
            for m in matches if "metadata" in m
        ])
        sources = [m["metadata"].get("source", "Unknown") for m in matches]

        # 4️⃣ Generate AI response
        ai_payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a factual, performance-focused bodybuilding assistant trained "
                        "on Forged by Freedom transcripts. Be clear, complete, and direct."
                    ),
                },
                {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
            ],
        }

        chat_url = f"{OPENROUTER_BASE_URL}/chat/completions"
        ai_resp = requests.post(
            chat_url,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=ai_payload,
            timeout=60,
        )
        ai_resp.raise_for_status()
        answer = ai_resp.json()["choices"][0]["message"]["content"]

        # 5️⃣ Return result
        return jsonify({
            "query": query,
            "response": answer,
            "sources": sources,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "✅ Forged by Freedom Search API ready",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "time": datetime.utcnow().isoformat() + "Z"
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=True)
