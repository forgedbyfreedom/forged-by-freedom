#!/usr/bin/env python3
"""
app.py — Forged by Freedom Search + Unfiltered AI Engine
─────────────────────────────────────────────────────────
Connects:
    🧠 Pinecone vector database
    🔎 OpenRouter (Nous Hermes 2 Pro or other model)
    🌐 Flask API (for local or GitHub Actions deployment)
"""

from flask import Flask, request, jsonify, render_template
from pinecone import Pinecone
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

# ============================================================
# ✅ Load environment variables early
# ============================================================
load_dotenv()

# ============================================================
# 🧩 Flask app
# ============================================================
app = Flask(__name__)

# ============================================================
# 🔐 Environment variables
# ============================================================
PINECONE_API_KEY = os.getenv("PINECONEAPI")  # ✅ fixed: matches your env var
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-2-pro")
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")  # for 3072-dim

# === Verify keys ===
if not PINECONE_API_KEY:
    raise ValueError("❌ Missing Pinecone API key (PINECONEAPI). Check .env file.")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ Missing OpenRouter API key.")

# ============================================================
# 🔌 Initialize Pinecone
# ============================================================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)
print(f"✅ Connected to Pinecone index: {PINECONE_INDEX_NAME}")

# ============================================================
# 🔎 API Routes
# ============================================================

@app.route("/api/search", methods=["POST"])
def api_search():
    """Perform semantic search and generate AI answer."""
    try:
        data = request.json or {}
        query = data.get("query", "").strip()
        top_k = int(data.get("top_k", 5))

        if not query:
            return jsonify({"error": "Missing query"}), 400

        # Step 1️⃣: Create embedding via OpenRouter
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

        # Step 2️⃣: Query Pinecone
        results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
        matches = results.get("matches", [])

        if not matches:
            return jsonify({"response": "No results found in the index."}), 200

        # Step 3️⃣: Build context
        context = "\n\n".join([
            m["metadata"].get("text", "")[:1500]
            for m in matches if "metadata" in m
        ])
        sources = [m["metadata"].get("source", "Unknown") for m in matches]

        # Step 4️⃣: Generate AI response
        ai_payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a direct, unfiltered bodybuilding research assistant "
                        "trained on Forged by Freedom transcripts. Include relevant context "
                        "and reference specific source material when possible."
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

        # Step 5️⃣: Return result
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
    """Simple home route"""
    return jsonify({
        "status": "ok",
        "message": "✅ Forged by Freedom AI Search online",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "time": datetime.utcnow().isoformat() + "Z"
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"})


@app.route("/ui")
def ui():
    """Optional front-end endpoint"""
    return render_template("search.html")

# ============================================================
# 🚀 Run Server
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=True)
