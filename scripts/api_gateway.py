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

# Validate environment variables
if not openai.api_key:
    raise ValueError("Missing OpenAI API key: Ensure 'OPENROUTER_API_KEY' is set in your environment.")
if not pinecone_api_key:
    raise ValueError("Missing Pinecone API key: Ensure 'PINECONE_API_KEY' is set in your environment.")

# Initialize Pinecone
try:
    pinecone.init(api_key=pinecone_api_key, environment="us-east-1")  # Adjust the environment if needed
    index = pinecone.Index("forged-freedom-ai")
    print(index.describe_index_stats())  # Optional: Confirm index statistics
except Exception as e:
    raise ValueError(f"Pinecone initialization failed: {e}")

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Forged by Freedom API live"})

# Fix the decorator for the /query route
@app.route("/query", methods=["POST"])
def query_pinecone():
    data = request.json
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    # Debugging logs
    print(f"Received query: {query}")

    # Embed query via OpenAI
    try:
        print("Calling OpenAI API...")
        response = openai.Embedding.create(
            model="text-embedding-3-large",
            input=query
        )
        embed = response["data"][0]["embedding"]
        print(f"Generated embedding: {embed[:10]}...")  # Print the first 10 dimensions of the embedding
    except Exception as e:
        print(f"Error in OpenAI embedding creation: {e}")
        return jsonify({"error": "Failed to generate embedding", "details": str(e)}), 500

    # Search Pinecone
    try:
        print("Querying Pinecone...")
        res = index.query(vector=embed, top_k=5, include_metadata=True)
        print(f"Pinecone response: {res}")
    except Exception as e:
        print(f"Error in Pinecone query: {e}")
        return jsonify({"error": "Failed to query Pinecone", "details": str(e)}), 500

    # If no errors occur
    return jsonify(res.to_dict())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
