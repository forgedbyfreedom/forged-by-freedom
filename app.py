#!/usr/bin/env python3
"""
Forged By Freedom AI Coach API
- Pinecone (v3) vector search
- OpenRouter embeddings + chat completions
- Simple Flask API for Wix/HTML front-end

Endpoints:
  GET  /health
  GET  /stats
  POST /search   { "query": "...", "top_k": 5 }
"""

import os
import json
from pathlib import Path
from datetime import datetime

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from pinecone import Pinecone


# ---------- dotenv (Python 3.14-safe) ----------
ENV_PATH = Path(__file__).resolve().parent / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    # still allow Render env vars
    load_dotenv(override=True)


# ---------- config ----------
PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
PINECONE_INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or "forged-transcripts").strip()

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "nousresearch/hermes-2-pro").strip()
OPENROUTER_EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
STATS_PATH = Path(__file__).resolve().parent / "stats.json"

PORT = int(os.getenv("PORT", "5051"))

if not PINECONE_API_KEY:
    raise RuntimeError("Missing PINECONE_API_KEY in environment (.env or Render env vars)")
if not OPENROUTER_API_KEY:
    raise RuntimeError("Missing OPENROUTER_API_KEY in environment (.env or Render env vars)")


# ---------- clients ----------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)


# ---------- app ----------
app = Flask(__name__)
CORS(app)


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def openrouter_headers():
    # OpenRouter recommends including optional headers; harmless if omitted.
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forgedbyfreedom.org",
        "X-Title": "Forged By Freedom AI Coach",
    }


@app.get("/")
def root():
    return jsonify(
        {
            "status": "ok",
            "time": utc_now(),
            "pinecone_index": PINECONE_INDEX_NAME,
            "openrouter_model": OPENROUTER_MODEL,
            "embed_model": OPENROUTER_EMBED_MODEL,
        }
    )


@app.get("/health")
def health():
    """
    Quick health check.
    - Always returns 200 if Flask is up.
    - Includes optional upstream checks (Pinecone + OpenRouter).
    """
    out = {"status": "ok", "time": utc_now(), "checks": {}}

    # Pinecone check: describe index (fast)
    try:
        desc = pc.describe_index(PINECONE_INDEX_NAME)
        out["checks"]["pinecone"] = {"ok": True, "name": desc.get("name", PINECONE_INDEX_NAME)}
    except Exception as e:
        out["checks"]["pinecone"] = {"ok": False, "error": str(e)}

    # OpenRouter check: lightweight (models endpoint)
    try:
        r = requests.get(f"{OPENROUTER_BASE_URL}/models", headers=openrouter_headers(), timeout=15)
        out["checks"]["openrouter"] = {"ok": r.ok, "status_code": r.status_code}
        if not r.ok:
            out["checks"]["openrouter"]["error"] = r.text[:200]
    except Exception as e:
        out["checks"]["openrouter"] = {"ok": False, "error": str(e)}

    return jsonify(out)


@app.get("/stats")
def stats():
    if not STATS_PATH.exists():
        return jsonify({"summary": {"channels": 0, "episodes": 0, "total_words": 0}, "channels": []})

    with STATS_PATH.open("r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.post("/search")
def search():
    payload = request.get_json(force=True, silent=True) or {}
    query = (payload.get("query") or "").strip()
    top_k = int(payload.get("top_k") or 5)

    if not query:
        return jsonify({"error": "Missing 'query'"}), 400

    # 1) Embed with OpenRouter
    try:
        emb_resp = requests.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers=openrouter_headers(),
            json={"model": OPENROUTER_EMBED_MODEL, "input": query},
            timeout=30,
        )
        if not emb_resp.ok:
            return jsonify({"error": "Embedding request failed", "details": emb_resp.text[:500]}), 502

        emb_json = emb_resp.json()
        embedding = emb_json["data"][0]["embedding"]
    except Exception as e:
        return jsonify({"error": "Embedding exception", "details": str(e)}), 502

    # 2) Query Pinecone
    try:
        res = index.query(vector=embedding, top_k=top_k, include_metadata=True)
        matches = res.get("matches", []) if isinstance(res, dict) else getattr(res, "matches", [])
    except Exception as e:
        return jsonify({"error": "Pinecone query failed", "details": str(e)}), 502

    chunks = []
    sources = []
    for m in matches:
        md = (m.get("metadata") or {}) if isinstance(m, dict) else (getattr(m, "metadata", {}) or {})
        text = (md.get("text") or "").strip()
        if text:
            chunks.append(text[:1500])
        sources.append(md.get("source") or md.get("title") or "Unknown")

    context = "\n\n---\n\n".join(chunks) if chunks else ""

    # 3) Chat completion with OpenRouter
    system = (
        "You are the Forged By Freedom AI Coach. "
        "Use the provided context when available. "
        "If context is insufficient, say so and give best-practice guidance without fabricating citations."
    )

    user_msg = f"QUESTION:\n{query}\n\nCONTEXT:\n{context}"

    try:
        chat_resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=openrouter_headers(),
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.4,
            },
            timeout=75,
        )

        if not chat_resp.ok:
            return jsonify({"error": "Chat request failed", "details": chat_resp.text[:500]}), 502

        chat_json = chat_resp.json()
        answer = chat_json["choices"][0]["message"]["content"]
    except Exception as e:
        return jsonify({"error": "Chat exception", "details": str(e)}), 502

    return jsonify(
        {
            "query": query,
            "response": answer,
            "sources": sources,
            "top_k": top_k,
            "timestamp": utc_now(),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

