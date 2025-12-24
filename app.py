#!/usr/bin/env python3
"""
Forged By Freedom AI Coach API
- Pinecone v3/v4+ compatible (Pinecone class)
- OpenRouter via OpenAI SDK base_url
- Works locally (.env) and on Render (env vars)
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from pinecone import Pinecone
from openai import OpenAI


# ------------------ ENV ------------------
def load_env():
    """
    Load .env ONLY if present. On Render, env vars are injected so this is harmless.
    Explicit path prevents dotenv issues in newer Python.
    """
    repo_root = Path(__file__).resolve().parent
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)

load_env()

# Support both var names (you have both in different places historically)
PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
PINECONE_INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or os.getenv("PINECONE_INDEX_NAME") or os.getenv("PINECONE_INDEX") or "forged-freedom-ai").strip()
PINECONE_INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or os.getenv("PINECONE_INDEX_NAME") or os.getenv("PINECONE_INDEX") or "forged-freedom-ai").strip()

# If you’ve standardized on PINECONE_INDEX_NAME, keep it:
PINECONE_INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()

OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "nousresearch/hermes-3-llama-3.1-70b").strip()
OPENROUTER_EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

PORT = int(os.getenv("PORT", "5051"))

# where your scripts write stats
STATS_PATH = os.getenv("STATS_PATH", "transcripts/stats.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_env(name: str, value: str):
    if not value:
        raise RuntimeError(f"Missing {name}. Set it in Render env vars or local .env")


require_env("PINECONE_API_KEY", PINECONE_API_KEY)
require_env("OPENROUTER_API_KEY", OPENROUTER_API_KEY)


# ------------------ CLIENTS ------------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

or_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


# ------------------ APP ------------------
app = Flask(__name__)
CORS(app)


@app.get("/")
def root():
    return jsonify(
        {
            "status": "ok",
            "service": "forged-by-freedom-ai",
            "index": PINECONE_INDEX_NAME,
            "model": OPENROUTER_MODEL,
            "embed_model": OPENROUTER_EMBED_MODEL,
            "time": now_iso(),
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": now_iso()})


@app.get("/stats")
def stats():
    if not os.path.exists(STATS_PATH):
        return jsonify(
            {
                "summary": {"channels": 0, "episodes": 0, "total_words": 0},
                "channels": [],
                "last_updated": None,
            }
        )

    with open(STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


def embed_query(text: str) -> List[float]:
    resp = or_client.embeddings.create(model=OPENROUTER_EMBED_MODEL, input=text)
    return resp.data[0].embedding


def chat_answer(user_query: str, context: str) -> str:
    resp = or_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": "You are the Forged By Freedom AI Coach."},
            {
                "role": "user",
                "content": f"Question:\n{user_query}\n\nUse this context:\n{context}",
            },
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content


@app.get("/search")
def search_help():
    # Prevent 405 confusion in browsers/Wix preview tools.
    return jsonify(
        {
            "ok": True,
            "message": "Use POST /search with JSON: { 'query': '...', 'top_k': 5 }",
            "example_curl": "curl -X POST /search -H 'Content-Type: application/json' -d '{\"query\":\"test\",\"top_k\":5}'",
        }
    ), 200


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

        chunks: List[str] = []
        sources: List[str] = []

        for m in (res.get("matches") or []):
            md = m.get("metadata") or {}
            txt = md.get("text") or ""
            if txt:
                chunks.append(txt[:1800])
            sources.append(md.get("source") or md.get("filename") or md.get("title") or "Unknown")

        context = "\n\n---\n\n".join(chunks) if chunks else ""
        answer = chat_answer(query, context) if context else "No matching transcript context was found in the index."

        return jsonify(
            {
                "query": query,
                "response": answer,
                "sources": sources,
                "timestamp": now_iso(),
                "top_k": top_k,
            }
        )
    except Exception as e:
        msg = str(e)
        if "Unauthorized" in msg or "Invalid API Key" in msg:
            return jsonify(
                {
                    "error": "Pinecone auth failed",
                    "details": "PINECONE_API_KEY is invalid for this Pinecone project OR the wrong key is deployed on Render.",
                }
            ), 401
        return jsonify({"error": "Search failed", "details": msg}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
