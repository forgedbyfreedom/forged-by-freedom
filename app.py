#!/usr/bin/env python3
import os, json, requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv(override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
CHAT_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-2-pro")
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")

STATS_PATH = "stats.json"

if not all([PINECONE_API_KEY, PINECONE_INDEX_NAME, OPENROUTER_API_KEY]):
    raise RuntimeError("❌ Missing required environment variables")

# ---- Pinecone ----
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# ---- Flask ----
app = Flask(__name__)
CORS(app)

def now():
    return datetime.utcnow().isoformat() + "Z"

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": now()})

@app.route("/stats")
def stats():
    if not os.path.exists(STATS_PATH):
        return jsonify({"summary": {"channels": 0, "episodes": 0, "total_words": 0}})
    with open(STATS_PATH, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))

@app.route("/search", methods=["POST"])
def search():
    q = request.json.get("query", "").strip()
    top_k = int(request.json.get("top_k", 5))

    if not q:
        return jsonify({"error": "Missing query"}), 400

    emb = requests.post(
        f"{OPENROUTER_BASE}/embeddings",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={"model": EMBED_MODEL, "input": q},
        timeout=30
    ).json()["data"][0]["embedding"]

    res = index.query(vector=emb, top_k=top_k, include_metadata=True)

    context, sources = [], []
    for m in res.get("matches", []):
        md = m["metadata"]
        context.append(md.get("text", "")[:1200])
        sources.append(md.get("source", "Unknown"))

    chat = requests.post(
        f"{OPENROUTER_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": CHAT_MODEL,
            "messages": [
                {"role": "system", "content": "You are the Forged By Freedom AI Coach."},
                {"role": "user", "content": q + "\n\n" + "\n".join(context)}
            ],
            "temperature": 0.4
        },
        timeout=60
    ).json()

    return jsonify({
        "query": q,
        "response": chat["choices"][0]["message"]["content"],
        "sources": sources,
        "timestamp": now()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5051)))
