#!/usr/bin/env python3
"""
api_gateway.py — Forged by Freedom
Wix → API → OpenAI + Pinecone bridge
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os, openai, pinecone

app = Flask(__name__)
CORS(app)

# Load API keys from environment
openai.api_key = os.getenv("OPENROUTER_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")

pc = pinecone.Pinecone(api_key=pinecone_api_key)
index = pc.Index("forged-freedom")

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Forged by Freedom API live"})

@app.route("/query", methods=["POST"])
def query_pinecone():
    data = request.json
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    # Embed query via OpenAI
    embed = openai.embeddings.create(
        model="text-embedding-3-large",
        input=query
    ).data[0].embedding

    # Search Pinecone
    res = index.query(vector=embed, top_k=5, include_metadata=True)
    return jsonify(res.to_dict())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
