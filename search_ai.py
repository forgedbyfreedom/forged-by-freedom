#!/usr/bin/env python3
import os
import openai
from pinecone import Pinecone
from dotenv import load_dotenv

# === Load Environment ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

INDEX_NAME = "forged-freedom-ai"
index = pc.Index(INDEX_NAME)

print("🧠 Ask your question:")
query = input("> ")

# Embed query
embedding = openai.embeddings.create(
    input=query,
    model="text-embedding-3-small"
).data[0].embedding

# Query Pinecone
results = index.query(
    vector=embedding,
    top_k=5,
    include_metadata=True
)

# Build context
context = "\n\n".join(
    [f"Excerpt {i+1}:\n{res['metadata']['path']}" for i, res in enumerate(results['matches'])]
)

# Ask OpenAI with context
prompt = f"""
You are an expert assistant for bodybuilding, fitness, and health.
Answer the question using the most relevant information below.

Question: {query}

Context:
{context}
"""

completion = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
)

print("\n💬 AI Response:\n")
print(completion.choices[0].message.content)
