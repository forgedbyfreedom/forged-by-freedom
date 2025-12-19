#!/usr/bin/env python3
import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone

# ============================================================
# 🔐 ENVIRONMENT VARIABLES (REQUIRED)
# ============================================================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_PATH = os.path.join(BASE_DIR, "..", "stats.json")

# ============================================================
# 🚀 FLASK APP
# ============================================================
app = Flask(__name__)

# 🔥 CORS — THIS IS WHAT FIXES YOUR BLOCKING ISSUE
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False
)

# ============================================================
# 🧠 PINECONE (NEW SDK)
# ============================================================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# ============================================================
# 📊 STATS ENDPOINT (FOR HEADER)
# ============================================================
@app.route("/stats.json", methods=["GET"])
def stats():
    """
    Serves stats.json for the glowing header on the site.
    """
    try:
        if not os.path.exists(STATS_PATH):
            return jsonify({"error": "stats.json not found"}), 404

        with open(STATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 🔍 AI SEARCH ENDPOINT
# ============================================================
@app.route("/search", methods=["POST", "OPTIONS"])
def search():
    try:
        data = request.get_json(force=True)
        query = (data.get("query") or "").strip()
        top_k = int(data.get("top_k", 5))

        if not query:
            return jsonify({"error": "Missing query text"}), 400

        # 1️⃣ EMBED QUERY
        embed_resp = requests.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBED_MODEL,
                "input": query,
            },
            timeout=30,
        )
        embed_resp.raise_for_status()
        query_vector = embed_resp.json()["data"][0]["embedding"]

        # 2️⃣ QUERY PINECONE
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
        )

        matches = results.get("matches", [])
        if not matches:
            return jsonify({
                "query": query,
                "response": "No relevant results found.",
                "sources": [],
            })

        # 3️⃣ BUILD CONTEXT
        context_chunks = []
        sources = []

        for m in matches:
            meta = m.get("metadata", {})
            text = meta.get("text", "")
            source = meta.get("source", "Unknown")

            if text:
                context_chunks.append(text[:1200])
            sources.append(source)

        context = "\n\n".join(context_chunks)

        # 4️⃣ AI COMPLETION
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
                    {
                        "role": "user",
                        "content": f"Question: {query}\n\nContext:\n{context}",
                    },
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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 🌐 ROOT + HEALTH
# ============================================================
@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "✅ Forged by Freedom ST3 AI Search Engine is online",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "time": datetime.utcnow().isoformat() + "Z",
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "time": datetime.utcnow().isoformat() + "Z",
    })


# ============================================================
# 🏁 ENTRYPOINT
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port)
