#!/usr/bin/env python3
"""
api_gateway.py — Forged by Freedom
Wix → API → OpenAI + Pinecone bridge
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from pinecone import Pinecone, ServerlessSpec

# Initialize Flask app
@app.route("/query", methods=["POST"])
def query_pinecone():
    data = request.json
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    print(f"Received query: {query}")

    # Generate an embedding (replace this placeholder with actual OpenAI embedding logic)
    embed = [5.2] * 3072  # Placeholder for the correct dimension

    # Query Pinecone
    try:
        res = index.query(vector=embed, top_k=5, include_metadata=True)
    except Exception as e:
        print(f"Error querying Pinecone: {e}")
        return jsonify({"error": f"Pinecone query failed: {str(e)}"}), 500

    return jsonify(res.to_dict())


# Load API keys from environment variables
openai_api_key = os.getenv("OPENROUTER_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_index_name = "forged-freedom-ai"

# Validate API keys
if not openai_api_key:
    raise ValueError("Missing OpenAI API key: Ensure 'OPENROUTER_API_KEY' is set in your environment.")
if not pinecone_api_key:
    raise ValueError("Missing Pinecone API key: Ensure 'PINECONE_API_KEY' is set in your environment.")

# Initialize Pinecone client and ensure the index exists
print("Initializing Pinecone...")
try:
    pc = Pinecone(api_key=pinecone_api_key)

    # Check if the index exists, and create it if not
    if pinecone_index_name not in pc.list_indexes().names():
        print(f"Creating Pinecone index: {pinecone_index_name}")
        pc.create_index(
            name=pinecone_index_name,
            dimension=1536,  # Adjust based on your data
            metric="cosine",  # Example metric
            spec=ServerlessSpec(
                cloud="aws",  # Replace with your cloud provider
                region="us-east-1",  # Replace with your region
            )
        )

    # Retrieve the index
    index = pc.Index(pinecone_index_name)
    print(f"Pinecone index '{pinecone_index_name}' initialized.")

except Exception as e:
    raise ValueError(f"Pinecone initialization failed: {e}")

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Forged by Freedom API live"})

@app.route("/query", methods=["POST"])
def query_pinecone():
    data = request.json
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    print(f"Received query: {query}")

    # Generate an embedding (Replace with actual OpenAI embedding logic)
    embed = [0.0] * 1536  # Placeholder for the embedding vector

    # Query Pinecone
    try:
        res = index.query(vector=embed, top_k=5, include_metadata=True)
    except Exception as e:
        print(f"Error querying Pinecone: {e}")
        return jsonify({"error": f"Pinecone query failed: {str(e)}"}), 500

    return jsonify(res.to_dict())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
