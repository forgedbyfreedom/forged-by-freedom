#!/usr/bin/env python3
"""
Forged By Freedom AI Coach API
- Pinecone semantic search (v3+)
- OpenRouter embeddings + chat
- Stats endpoint for Wix
"""

import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone
from dotenv import load_dotenv

# -------------------------------------------------
# ENV
# -------------------------------------------------
load_dotenv(override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-2-pro").strip()
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large").strip()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
STATS_PATH = os.getenv("STATS_PATH", "stats.json")

PORT = int(os.getenv("PORT", "5051"))

# -------------------------------------------------
# VALIDATION
# -------------------------------------------------
if not PINECONE_API_KEY:
    raise RuntimeError("❌ Missing PINECONE_API_KEY")

if not PINECONE_INDEX_NAME:
    raise RuntimeError("❌ Missing PINECONE_INDEX_NAME")

if not OPENROUTER_API_KEY:
    raise RuntimeError("❌ Missing OPENROUTER_API_KEY")

# -------------------------------------------------
# PINECONE INIT (CORRECT FOR V3+)
# -------------------------------------------------
pc = Pinecone(api_key=PINECONE_API_KEY)

indexes = [i["name"] for i in pc.list_indexes()]
if PINECONE_INDEX_NAME not in indexes:
    raise RuntimeError(
        f"❌ Pinecone index '{PINECONE_INDEX_NAME}' not found. "
        f"Available: {indexes}"
    )

index = pc.Index(PINECONE_INDEX_NAME)

# -------------------------------------------------
# APP
# -------------------------------------------------
app = Flask(__name__)
CORS(app)

def now():
    return datetime.utcnow().isoformat() + "Z"

# -------------------------------------------------
# ROUTES
# -------------------------------------------------
@app.route("/")
def root():
    return jsonify({
        "status": "ok",
        "service": "Forged By Freedom AI Coach",
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
            "channels": [],
            "warning": "stats.json not found"
        })

    with open(STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return jsonify(data)

@app.route("/search", methods=["POST"])
def search():
    payload = request.get_json(force=True) or {}
    query = payload.get("query", "").strip()
    top_k = int(payload.get("top_k", 5))

    if not query:
        return jsonify({"error": "Missing query"}), 400

    # -------------------------------------------------
    # 1) EMBEDDING
    # -------------------------------------------------
    emb_resp = requests.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={"model": EMBED_MODEL, "input": query},
        timeout=45
    )

    if emb_resp.status_code >= 400:
        return jsonify({
            "error": "Embedding failed",
            "detail": emb_resp.text
        }), 502

    query_vector = emb_resp.json()["data"][0]["embedding"]

    # -------------------------------------------------
    # 2) PINECONE QUERY
    # -------------------------------------------------
    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True
    )

    matches = results.get("matches", [])
    if not matches:
        return jsonify({
            "query": query,
            "response": "No relevant transcript content found.",
            "sources": [],
            "timestamp": now()
        })

    context_chunks = []
    sources = []

    for m in matches:
        md = m.get("metadata", {})
        if md.get("text"):
            context_chunks.append(md["text"][:1200])
        sources.append(md.get("source") or md.get("title") or "Unknown")

    context = "\n\n".join(context_chunks)

    # -------------------------------------------------
    # 3) CHAT COMPLETION
    # -------------------------------------------------
    chat_resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the Forged By Freedom AI Coach. "
                        "Be direct, evidence-based, practical, and motivating. "
                        "Use transcript context when available."
                    )
                },
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nContext:\n{context}"
                }
            ],
            "temperature": 0.4
        },
        timeout=75
    )

    if chat_resp.status_code >= 400:
        return jsonify({
            "error": "Chat completion failed",
            "detail": chat_resp.text
        }), 502

    answer = chat_resp.json()["choices"][0]["message"]["content"]

    return jsonify({
        "query": query,
        "response": answer,
        "sources": sources[:top_k],
        "timestamp": now()
    })

# -------------------------------------------------
# MAIN
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
