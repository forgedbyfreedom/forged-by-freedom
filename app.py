#!/usr/bin/env python3
"""
Forged By Freedom AI Coach API
--------------------------------
• Pinecone SDK v3+
• OpenRouter via OpenAI SDK
• Explicit .env loading (local)
• Safe startup on Render
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from pinecone import Pinecone
from openai import OpenAI


# ============================================================
# 🔐 ENV LOADING (EXPLICIT — DO NOT CHANGE)
# ============================================================
REPO_ROOT = Path(__file__).resolve().parent
DOTENV_PATH = REPO_ROOT / ".env"

# Local dev → loads .env
# Render → no .env present, env vars already injected
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
PINECONE_INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()

OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "nousresearch/hermes-3-llama-3.1-70b").strip()
OPENROUTER_EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

PORT = int(os.getenv("PORT", "5051"))
STATS_PATH = os.getenv("STATS_PATH", "transcripts/stats.json")


# ============================================================
# 🧠 HELPERS
# ============================================================
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def have_required_env() -> bool:
    return bool(PINECONE_API_KEY and OPENROUTER_API_KEY)


def build_clients():
    """
    Lazy-build clients so the app can boot even if Pinecone is down.
    Returns: (pinecone_index, openrouter_client, error)
    """
    if not have_required_env():
        missing = []
        if not PINECONE_API_KEY:
            missing.append("PINECONE_API_KEY")
        if not OPENROUTER_API_KEY:
            missing.append("OPENROUTER_API_KEY")
        return None, None, f"Missing env vars: {', '.join(missing)}"

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
    except Exception as e:
        return None, None, f"Pinecone init failed: {e}"

    try:
        or_client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL
        )
    except Exception as e:
        return index, None, f"OpenRouter init failed: {e}"

    return index, or_client, None


def embed_query(or_client: OpenAI, text: str) -> List[float]:
    resp = or_client.embeddings.create(
        model=OPENROUTER_EMBED_MODEL,
        input=text
    )
    return resp.data[0].embedding


def chat_answer(or_client: OpenAI, question: str, context: str) -> str:
    resp = or_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        temperature=0.4,
        messages=[
            {"role": "system", "content": "You are the Forged By Freedom AI Coach."},
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nContext (quotes allowed):\n{context}",
            },
        ],
    )
    return resp.choices[0].message.content


# ============================================================
# 🚀 FLASK APP
# ============================================================
app = Flask(__name__)
CORS(app)


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
    index, or_client, err = build_clients()
    return jsonify({
        "status": "ok" if err is None else "degraded",
        "env_ok": have_required_env(),
        "pinecone_index": PINECONE_INDEX_NAME,
        "openrouter_base": OPENROUTER_BASE_URL,
        "error": err,
        "time": now_iso(),
    })


@app.get("/stats")
def stats():
    if not os.path.exists(STATS_PATH):
        return jsonify({
            "total_channels": 0,
            "total_episodes": 0,
            "total_words": 0,
            "last_updated": None,
        })

    with open(STATS_PATH, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.post("/search")
def search():
    data = request.get_json(force=True) or {}
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k") or 5)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    index, or_client, err = build_clients()
    if err or not index or not or_client:
        return jsonify({"error": "Service unavailable", "details": err}), 503

    try:
        qvec = embed_query(or_client, query)
        res = index.query(
            vector=qvec,
            top_k=top_k,
            include_metadata=True
        )

        chunks = []
        sources = []

        for m in res.get("matches", []):
            md = m.get("metadata", {})
            text = md.get("text")
            if text:
                chunks.append(text[:1800])
            sources.append(
                md.get("source")
                or md.get("filename")
                or md.get("episode")
                or "Unknown"
            )

        context = "\n\n---\n\n".join(chunks)
        answer = (
            chat_answer(or_client, query, context)
            if context
            else "No matching transcript context was found."
        )

        return jsonify({
            "query": query,
            "response": answer,
            "sources": sources,
            "top_k": top_k,
            "timestamp": now_iso(),
        })

    except Exception as e:
        return jsonify({"error": "Search failed", "details": str(e)}), 500


# ============================================================
# 🧯 ENTRYPOINT
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
