#!/usr/bin/env python3
"""
Forged By Freedom AI Coach API
- Pinecone SDK v3/v4+ (Pinecone class)
- OpenRouter via OpenAI SDK base_url
- Works locally (.env) and on Render (env vars)
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


from pinecone import Pinecone
from openai import OpenAI


# ------------------ ENV LOADING ------------------
# IMPORTANT:
# - Local dev: load .env from repo root explicitly
# - Render: there is usually no .env file, so this does nothing
REPO_ROOT = Path(__file__).resolve().parent
DOTENV_PATH = REPO_ROOT / ".env"
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
PINECONE_INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()

OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "nousresearch/hermes-3-llama-3.1-70b").strip()
OPENROUTER_EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

PORT = int(os.getenv("PORT", "5051"))
STATS_PATH = os.getenv("STATS_PATH", "transcripts/stats.json")


# ------------------ HELPERS ------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def have_required_env() -> bool:
    return bool(PINECONE_API_KEY and OPENROUTER_API_KEY)


def build_clients() -> tuple[Optional[Pinecone], Optional[object], Optional[OpenAI], Optional[str]]:
    """
    Returns (pc, pinecone_index, openrouter_client, error_string)
    """
    if not have_required_env():
        missing = []
        if not PINECONE_API_KEY:
            missing.append("PINECONE_API_KEY")
        if not OPENROUTER_API_KEY:
            missing.append("OPENROUTER_API_KEY")
        return None, None, None, f"Missing env: {', '.join(missing)}"

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        idx = pc.Index(PINECONE_INDEX_NAME)
    except Exception as e:
        return None, None, None, f"Pinecone init failed: {e}"

    try:
        or_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    except Exception as e:
        return pc, idx, None, f"OpenRouter client init failed: {e}"

    return pc, idx, or_client, None


def embed_query(or_client: OpenAI, text: str) -> List[float]:
    resp = or_client.embeddings.create(model=OPENROUTER_EMBED_MODEL, input=text)
    return resp.data[0].embedding


def chat_answer(or_client: OpenAI, user_query: str, context: str) -> str:
    resp = or_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": "You are the Forged By Freedom AI Coach."},
            {
                "role": "user",
                "content": f"Question:\n{user_query}\n\nUse this context (quotes allowed):\n{context}",
            },
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content


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
    pc, idx, or_client, err = build_clients()
    return jsonify(
        {
            "status": "ok" if err is None else "degraded",
            "time": now_iso(),
            "env_ok": have_required_env(),
            "pinecone_index": PINECONE_INDEX_NAME,
            "openrouter_base_url": OPENROUTER_BASE_URL,
            "error": err,
        }
    )


@app.get("/stats")
def stats():
    if not os.path.exists(STATS_PATH):
        return jsonify(
            {
                "total_channels": 0,
                "total_episodes": 0,
                "total_words": 0,
                "last_updated": None,
            }
        )

    with open(STATS_PATH, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.post("/search")
def search():
    data = request.get_json(force=True) or {}
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k") or 5)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    pc, idx, or_client, err = build_clients()
    if err is not None or idx is None or or_client is None:
        return jsonify({"error": "AI Coach unavailable", "details": err}), 503

    try:
        qvec = embed_query(or_client, query)
        res = idx.query(vector=qvec, top_k=top_k, include_metadata=True)

        chunks: List[str] = []
        sources: List[str] = []

        for m in (res.get("matches") or []):
            md = m.get("metadata") or {}
            txt = md.get("text") or ""
            if txt:
                chunks.append(txt[:1800])
            sources.append(md.get("source") or md.get("filename") or md.get("episode") or "Unknown")

        context = "\n\n---\n\n".join(chunks) if chunks else ""
        answer = chat_answer(or_client, query, context) if context else (
            "No matching transcript context was found in the index for that query."
        )

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
        return jsonify({"error": "Search failed", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
