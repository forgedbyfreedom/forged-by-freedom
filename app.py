#!/usr/bin/env python3
import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone

# ============================================================
# 🔐 ENV
# ============================================================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")

# ============================================================
# 🚀 APP
# ============================================================
app = Flask(__name__)

# 🔥 HARD CORS (THIS IS THE KEY)
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"]
)

# ============================================================
# 🧠 PINECONE
# ============================================================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# ============================================================
# 🔍 SEARCH
# ============================================================
@app.route("/search", methods=["POST", "OPTIONS"])
def search():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    data = request.get_json(force=True)
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k", 5))

    if not query:
        return jsonify({"error": "Missing query"}), 400

    # 1️⃣ Embed query
    embed = requests.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBED_MODEL, "input": query},
        timeout=30,
    )
    embed.raise_for_status()
    vector = embed.json()["data"][0]["embedding"]

    # 2️⃣ Pinecone search
    results = index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True
    )

    matches = results.get("matches", [])
    if not matches:
        return jsonify({
            "query": query,
            "response": "No relevant results found.",
            "sources": []
        })

    context = []
    sources = []

    for m in matches:
        meta = m.get("metadata", {})
        if meta.get("text"):
            context.append(meta["text"][:1200])
        sources.append(meta.get("source", "Unknown"))

    # 3️⃣ AI answer
    ai = requests.post(
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
                        "You are a no-nonsense bodybuilding AI coach. "
                        "Use Forged by Freedom transcripts. Be concise, direct, and useful."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nContext:\n{chr(10).join(context)}",
                },
            ],
        },
        timeout=60,
    )
    ai.raise_for_status()

    answer = ai.json()["choices"][0]["message"]["content"]

    return jsonify({
        "query": query,
        "response": answer,
        "sources": sources,
        "time": datetime.utcnow().isoformat() + "Z",
    })

# ============================================================
# 🌐 HEALTH
# ============================================================
@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "✅ Forged by Freedom ST3 AI Search Engine is online",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ============================================================
# 🏁 ENTRY
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port)
