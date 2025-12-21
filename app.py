#!/usr/bin/env python3
"""
Forged By Freedom AI Coach API
Clean, Pinecone v3 compatible
"""

import os, json, requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone
from dotenv import load_dotenv

# ------------------ ENV ------------------
load_dotenv(override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "nousresearch/hermes-2-pro"
EMBED_MODEL = "text-embedding-3-large"
STATS_PATH = "stats.json"

if not PINECONE_API_KEY or not OPENROUTER_API_KEY:
    raise RuntimeError("Missing required API keys")

# ------------------ PINECONE ------------------
pc = Pinecone(api_key=PINECONE_API_KEY)
# ------------------ APP ------------------
app = Flask(__name__)
CORS(app)

def now():
    return datetime.utcnow().isoformat() + "Z"

@app.route("/")
def root():
    return jsonify({
        "status": "ok",
        "index": PINECONE_INDEX_NAME,
        "time": now()
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "time": now()})

@app.route("/stats")
def stats():
    if not os.path.exists(STATS_PATH):
        return jsonify({
            "summary": {"channels": 0, "episodes": 0, "total_words": 0},
            "channels": []
        })
    with open(STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/search", methods=["POST"])
def search():
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    top_k = int(data.get("top_k", 5))

    if not query:
        return jsonify({"error": "Missing query"}), 400

    # Embed
    emb = requests.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={"model": EMBED_MODEL, "input": query},
        timeout=30
    ).json()["data"][0]["embedding"]

    # Query Pinecone
    res = index.query(vector=emb, top_k=top_k, include_metadata=True)

    chunks, sources = [], []
    for m in res.get("matches", []):
        md = m.get("metadata", {})
        if md.get("text"):
            chunks.append(md["text"][:1200])
        sources.append(md.get("source", "Unknown"))

    context = "\n\n".join(chunks)

    # Chat
    chat = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": "You are the Forged By Freedom AI Coach."},
                {"role": "user", "content": f"{query}\n\nContext:\n{context}"}
            ],
            "temperature": 0.4
        },
        timeout=60
    ).json()

    answer = chat["choices"][0]["message"]["content"]

    return jsonify({
        "query": query,
        "response": answer,
        "sources": sources,
        "timestamp": now()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5051)))
