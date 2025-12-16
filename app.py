#!/usr/bin/env python3
"""
app.py — Forged by Freedom AI Coach API
──────────────────────────────────────────────
Integrates:
  🧠 Pinecone vector database (v8+ SDK)
  🤖 OpenRouter (Nous Hermes 2 Pro)
  🌐 Flask API for Wix AI Coach Integration
"""

import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone
from dotenv import load_dotenv

# ============================================================
# 🔐 Load Environment Variables
# ============================================================
load_dotenv(dotenv_path=".env", override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-2-pro").strip()
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large").strip()

if not PINECONE_API_KEY or not OPENROUTER_API_KEY:
    raise ValueError("❌ Missing required API keys. Check your .env or GitHub Secrets.")

print(f"🔑 Pinecone Key Prefix: {PINECONE_API_KEY[:10]}... | Env: {PINECONE_ENVIRONMENT}")
print(f"📦 Index: {PINECONE_INDEX_NAME} | Model: {OPENROUTER_MODEL}")

# ============================================================
# 🔌 Initialize Pinecone Connection
# ============================================================
try:
    pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
    indexes = [idx["name"] for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in indexes:
        raise ValueError(f"❌ Index '{PINECONE_INDEX_NAME}' not found. Available: {indexes}")

    index = pc.Index(PINECONE_INDEX_NAME)
    print(f"✅ Connected to Pinecone index: {PINECONE_INDEX_NAME}")

except Exception as e:
    raise RuntimeError(f"❌ Pinecone connection failed: {e}")

# ============================================================
# ⚙️ Flask Setup
# ============================================================
app = Flask(__name__)
CORS(app)

# ============================================================
# 🧠 Search + AI Endpoint
# ============================================================
@app.route("/search", methods=["POST"])
def search():
    """Perform semantic search + AI response."""
    try:
        data = request.get_json(force=True)
        query = (data.get("query") or "").strip()
        top_k = int(data.get("top_k", 5))

        if not query:
            return jsonify({"error": "Missing query text"}), 400

        # === 1️⃣ Embed Query ===
        embed_resp = requests.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={"model": EMBED_MODEL, "input": query},
            timeout=30,
        )
        embed_resp.raise_for_status()
        query_vector = embed_resp.json()["data"][0]["embedding"]

        # === 2️⃣ Query Pinecone ===
        results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
        matches = results.get("matches", [])
        if not matches:
            return jsonify({"response": "No relevant results found."}), 200

        # === 3️⃣ Build Context ===
        context = "\n\n".join([
            m["metadata"].get("text", "")[:1200]
            for m in matches if "metadata" in m
        ])
        sources = [m["metadata"].get("source", "Unknown") for m in matches]

        # === 4️⃣ AI Completion ===
        ai_resp = requests.post(
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
                            "You are a high-performance bodybuilding AI coach trained "
                            "on Forged by Freedom transcripts. Give concise, science-based, "
                            "and motivational answers."
                        ),
                    },
                    {"role": "user", "content": f"Question: {query}\n\nContext:\n{context}"}
                ],
            },
            timeout=60,
        )
        ai_resp.raise_for_status()
        answer = ai_resp.json()["choices"][0]["message"]["content"]

        return jsonify({
            "query": query,
            "response": answer,
            "sources": sources,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Network error: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# 🌐 Health Check Routes
# ============================================================
@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "✅ Forged by Freedom AI Coach API running",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "time": datetime.utcnow().isoformat() + "Z"
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"})

# ============================================================
# 🚀 Entry Point
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=True)
