#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone
from typing import List

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from pathlib import Path

from pinecone import Pinecone
from openai import OpenAI

# ================= ENV =================
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-3-llama-3.1-70b")
OPENROUTER_EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")

PORT = int(os.getenv("PORT", "5051"))

if not PINECONE_API_KEY:
    raise RuntimeError("❌ PINECONE_API_KEY missing after dotenv load")

if not OPENROUTER_API_KEY:
    raise RuntimeError("❌ OPENROUTER_API_KEY missing after dotenv load")

print("✅ Pinecone key loaded:", PINECONE_API_KEY[:8], "…")

# ================= CLIENTS =================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

or_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL
)

# ================= APP =================
app = Flask(__name__)
CORS(app)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return jsonify({
        "status": "ok",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "time": now_iso()
    })

@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": now_iso()})

def embed_query(text: str) -> List[float]:
    resp = or_client.embeddings.create(
        model=OPENROUTER_EMBED_MODEL,
        input=text
    )
    return resp.data[0].embedding

def chat_answer(query: str, context: str) -> str:
    resp = or_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": "You are the Forged By Freedom AI Coach."},
            {"role": "user", "content": f"{query}\n\nContext:\n{context}"}
        ],
        temperature=0.4
    )
    return resp.choices[0].message.content

@app.post("/search")
def search():
    data = request.get_json(force=True) or {}
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k") or 5)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    qvec = embed_query(query)
    res = index.query(vector=qvec, top_k=top_k, include_metadata=True)

    chunks = []
    sources = []

    for m in res.get("matches", []):
        md = m.get("metadata", {})
        if md.get("text"):
            chunks.append(md["text"][:1800])
        sources.append(md.get("source", "unknown"))

    context = "\n\n---\n\n".join(chunks)
    answer = chat_answer(query, context) if context else "No relevant transcript found."

    return jsonify({
        "query": query,
        "response": answer,
        "sources": sources,
        "timestamp": now_iso()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
