from pinecone import Pinecone
import os

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

SEARCH_TERM = "Olympia"  # <-- change this to whatever text you want to search

print(f"🔍 Searching for vectors containing '{SEARCH_TERM}'...")

res = index.query(vector=[0]*3072, top_k=10000, include_metadata=True)
matches = [
    {
        "id": v["id"],
        "source": v["metadata"].get("source", ""),
        "chunk": v["metadata"].get("chunk", "")
    }
    for v in res.get("matches", [])
    if SEARCH_TERM.lower() in str(v["metadata"]).lower()
]

if matches:
    print(f"✅ Found {len(matches)} vectors:")
    for m in matches[:20]:  # show first 20
        print(f" - {m['id']}  ({m['source']})")
else:
    print("❌ No matches found.")
