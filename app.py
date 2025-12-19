import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from pinecone import Pinecone

# ============================================================
# 🔧 Environment
# ============================================================
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/nous-hermes-2-mixtral-8x7b-dpo")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# ============================================================
# 🚀 App
# ============================================================
app = Flask(__name__)

# 🔥 THIS FIXES YOUR PROBLEM
CORS(app, resources={r"/*": {"origins": "*"}})

# ============================================================
# 🌲 Pinecone Init (NEW SDK)
# ============================================================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# ============================================================
# 🔍 SEARCH ENDPOINT
# ============================================================
@app.route("/search", methods=["POST"])
def search():
    try:
        data = request.get_json(force=True)
        query = (data.get("query") or "").strip()
        top_k = int(data.get("top_k", 5))

        if not query:
            return jsonify({"error": "Missing query"}), 400

        # === 1️⃣ Embed query
        embed_resp = requests.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": EMBED_MODEL,
                "input": query
            },
            timeout=30
        )
        embed_resp.raise_for_status()
        vector = embed_resp.json()["data"][0]["embedding"]

        # === 2️⃣ Pinecone query
        res = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True
        )

        matches = res.get("matches", [])

        if not matches:
            return jsonify({
                "aiAnswer": "No relevant results found.",
                "results": []
            })

        # === 3️⃣ Build context
        context_chunks = []
        results = []

        for m in matches:
            meta = m.get("metadata", {})
            text = meta.get("text", "")
            source = meta.get("source", "Unknown")

            if text:
                context_chunks.append(text[:1200])

            results.append({
                "title": source,
                "snippet": text[:300]
            })

        context = "\n\n".join(context_chunks)

        # === 4️⃣ AI completion
        ai_resp = requests.post(
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
                            "You are Forged by Freedom’s elite bodybuilding AI coach. "
                            "Answer clearly, concisely, with authority, science, and motivation."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Question:\n{query}\n\nContext:\n{context}"
                    }
                ]
            },
            timeout=60
        )
        ai_resp.raise_for_status()
        ai_answer = ai_resp.json()["choices"][0]["message"]["content"]

        return jsonify(
