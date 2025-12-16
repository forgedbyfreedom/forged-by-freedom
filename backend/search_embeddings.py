from pinecone import Pinecone
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# === INIT CLIENTS ===
client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

print(f"✅ Connected to Pinecone index: {PINECONE_INDEX_NAME}")

def embed_text(text: str):
    """Create embedding from OpenRouter (OpenAI-compatible endpoint)."""
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    ).data[0].embedding
    return emb

def search(query: str, top_k: int = 5):
    """Search similar entries in Pinecone index."""
    query_emb = embed_text(query)
    results = index.query(vector=query_emb, top_k=top_k, include_metadata=True)
    print("\n🔍 Search Results:")
    for match in results["matches"]:
        print(f"  - {match['metadata'].get('title', 'Untitled')} (Score: {match['score']:.4f})")
    return results

if __name__ == "__main__":
    # Example test query
    q = input("Enter your search query: ")
    search(q)
