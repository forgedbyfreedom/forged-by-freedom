#!/usr/bin/env python3
"""
app.py — Forged by Freedom AI Coach Search API
──────────────────────────────────────────────
Connects:
    🧠 Pinecone vector database
    🤖 OpenRouter (Nous Hermes 2 Pro or other model)
    🌐 Flask API for Wix AI Coach Page
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()  # <-- ensure this is called before using env vars

api_key = os.getenv("PINECONE_API_KEY", "").strip()
environment = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws").strip()

print(f"🔑 Using Pinecone key prefix: {api_key[:10]}... | Env: {environment}")

pc = Pinecone(api_key=api_key, environment=environment)

# ============================================================
# 🔐 Environment variables
# ============================================================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-2-pro")
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-small")

if not PINECONE_API_KEY or not OPENROUTER_API_KEY:
    raise ValueError("❌ Missing required API keys. Check your .env or GitHub Secrets.")

# ============================================================
# 🔌 Initialize Pinecone
# ============================================================
try:
    pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
    index = pc.Index(PINECONE_INDEX_NAME)
    print(f"✅ Connected to Pinecone index: {PINECONE_INDEX_NAME}")
except Exception as e:
    raise RuntimeError(f"❌ Pinecone connection failed: {e}")

# ============================================================
# ⚙️ Flask App Configuration
# ============================================================
app = Flask(__name__)
CORS(app)  # enable requests from Wix front-end

# ============================================================
# 🧠 Semantic Search + AI Endpoint
# ============================================================
@app.route("/search", methods=["POST"])
def search():
    """Search the Pinecone index and return AI contextual response."""
    try:
        data = request.get_json() or {}
        query = data.get("query", "").strip()
        top_k = int(data.get("top_k", 5))

        if not query:
            return jsonify({"error": "Missing query text"}), 400

        # === 1️⃣ Create embedding from OpenRouter ===
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
            return jsonify({"response": "No matches found."}), 200

        # === 3️⃣ Build context from matched docs ===
        context = "\n\n".join([
            m["metadata"].get("text", "")[:1500]
            for m in matches if "metadata" in m
        ])
        sources = [m["metadata"].get("source", "Unknown") for m in matches]

        # === 4️⃣ Generate AI response via OpenRouter ===
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
                            "You are a high-performance bodybuilding AI coach. "
                            "Answer based on real Forged by Freedom transcripts, "
                            "using concise, factual, and motivational tone."
                        ),
                    },
                    {"role": "user", "content": f"Question: {query}\n\nContext:\n{context}"}
                ],
            },
            timeout=60,
        )
        ai_resp.raise_for_status()
        answer = ai_resp.json()["choices"][0]["message"]["content"]

        # === 5️⃣ Return formatted response ===
        return jsonify({
            "query": query,
            "response": answer,
            "sources": sources,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# 🌐 Health + Info Endpoints
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
# 🚀 Run Local
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=True)
