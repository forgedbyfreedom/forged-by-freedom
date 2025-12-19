import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import pinecone

# ============================================================
# 🔐 Environment
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/nous-hermes-2-mixtral-8x7b-dpo")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# ============================================================
# 🌐 App Init
# ============================================================
app = Flask(__name__)

# 🔥 THIS IS THE CRITICAL LINE 🔥
CORS(app, resources={r"/*": {"origins": "*"}})

# ============================================================
# 🧠 Pinecone Init
# ============================================================
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
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

        # 1️⃣ Embed query
        embed_resp = requests.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={"model": EMBED_MODEL, "input": query},
            timeout=30
        )
        embed_resp.raise_for_status()
        vector = embed_resp.json()["data"][0]["embedding"]

        # 2️⃣ Pinecone search
        result = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True
        )

        matches = result.get("matches", [])
        if not matches:
            return jsonify({
                "aiAnswer": "No relevant results found.",
                "results": []
            })

        # 3️⃣ Build context
        context_blocks = []
        results = []

        for m in matches:
            meta = m.get("metadata", {})
            text = meta.get("text", "")[:1200]
            source = meta.get("source", "Unknown")

            context_blocks.append(text)
            results.append({
                "title": source,
                "snippet": text[:300]
            })

        context = "\n\n".join(context_blocks)

        # 4️⃣ AI completion
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
                            "You are a high-performance bodybuilding AI coach trained on "
                            "Forged by Freedom transcripts. Give concise, science-based, "
                            "and motivational answers."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Question: {query}\n\nContext:\n{context}"
                    }
                ]
            },
            timeout=60
        )
        ai_resp.raise_for_status()

        answer = ai_resp.json()["choices"][0]["message"]["content"]

        return jsonify({
            "aiAnswer": answer,
            "results": results,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# ❤️ HEALTH CHECKS
# ============================================================
@app.route("/")
def root():
    return jsonify({
        "status": "ok",
        "message": "✅ Forged by Freedom ST3 AI Search Engine is online",
        "index": PINECONE_INDEX_NAME,
        "model": OPENROUTER_MODEL,
        "time": datetime.utcnow().isoformat() + "Z"
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ============================================================
# 🚀 RUN
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port)
