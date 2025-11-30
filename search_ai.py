#!/usr/bin/env python3
from openai import OpenAI
import pinecone, os

client = OpenAI()
pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment="us-east1-gcp")
index = pinecone.Index("forged-freedom-ai")

query = input("🧠 Ask your question: ")

# Create embedding for query
emb = client.embeddings.create(input=query, model="text-embedding-3-small").data[0].embedding

# Query Pinecone
results = index.query(vector=emb, top_k=5, include_metadata=True)

context = "\n\n".join([r["metadata"]["text"] for r in results["matches"]])

prompt = f"""
You are an expert bodybuilding, sports nutrition, and physiology assistant.

Answer the following question based on the content below.

Question: {query}

Relevant text:
{context}

Answer clearly, factually, and cite which experts the information came from.
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3,
)

print("\n💬 AI Response:")
print(response.choices[0].message.content)
