#!/usr/bin/env python3
"""
Forged By Freedom AI Coach API
- Pinecone v3+ compatible
- OpenRouter via OpenAI SDK
- Render-safe (no .env dependency in prod)
"""

import os
import json
from datetime import datetime, timezone
from typing import List

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from pinecone import Pinecone
from openai import OpenAI

# ------------------ ENV ------------------
# Safe: loads locally, ignored on Render
load_dotenv(override=True)

PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
PINECONE_INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()

OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "nousresearch/hermes-3-llama-3.1-70b").strip()
OPENROUTER_EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

PORT = int(os.getenv("PORT", "5051"))
STATS_PATH = os.getenv("STATS_PATH", "transcripts/stats.json")

# ---- HARD FAIL EARLY (NO MYSTERY ERRORS) ----
if not PINECONE_API_KEY:
    raise RuntimeError("❌ Missing PINECONE_API_KEY")

if not OPENROUTER_API_KEY:
    raise RuntimeError("❌ Missing OPENROUTER_API_KEY")

# ------------------ CLIENTS ------------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

or_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL
)

# ------------------ APP ------------------
app = Flask(__name__)
CORS(app)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
def root():
    return jsonify({
        "status": "ok",
        "service": "forged-by-freedom-ai",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "embed_model": OPENROUTER_EMBED_MODEL,
        "time": now_iso(),
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": now_iso()})


@app.get("/stats")
def stats():
    if not os.path.exists(STATS_PATH):
        return jsonify({
            "summary": {"channels": 0, "episodes": 0, "total_words": 0},
            "channels": [],
            "last_updated": None,
        })

    with open(STATS_PATH, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


def embed_query(text: str) -> List[float]:
    r = or_client.embeddings.create(
        model=OPENROUTER_EMBED_MODEL,
        input=text
    )
    return r.data[0].embedding


def chat_answer(question: str, context: str) -> str:
    r = or_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": "You are the Forged By Freedom AI Coach."},
            {"role": "user", "content": f"{question}\n\nContext:\n{context}"}
        ],
        temperature=0.4,
    )
    return r.choices[0].message.content


@app.post("/search")
def search():
    data = request.get_json(force=True) or {}
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k") or 5)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        qvec = embed_query(query)
        res = index.query(vector=qvec, top_k=top_k, include_metadata=True)

        chunks = []
        sources = []

        for m in res.get("matches", []):
            md = m.get("metadata") or {}
            txt = md.get("text", "")
            if txt:
                chunks.append(txt[:1800])
            sources.append(md.get("source") or md.get("filename") or "Unknown")

        context = "\n\n---\n\n".join(chunks)
        answer = chat_answer(query, context) if context else "No matching context found."

        return jsonify({
            "query": query,
            "response": answer,
            "sources": sources,
            "timestamp": now_iso(),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
