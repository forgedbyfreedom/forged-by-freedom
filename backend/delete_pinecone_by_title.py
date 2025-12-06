from pinecone import Pinecone
import os

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

DELETE_TERM = "Olympia"  # <-- change this

print(f"🧹 Searching for vectors containing '{DELETE_TERM}'...")

res = index.query(vector=[0]*3072, top_k=10000, include_metadata=True)
to_delete = [
    v["id"] for v in res.get("matches", [])
    if DELETE_TERM.lower() in str(v["metadata"]).lower()
]

if not to_delete:
    print("✨ No matching vectors found.")
else:
    index.delete(ids=to_delete)
    print(f"✅ Deleted {len(to_delete)} vectors containing '{DELETE_TERM}'.")
