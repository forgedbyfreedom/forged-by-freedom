from pinecone import Pinecone
import os
import string

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

valid_chars = set(string.ascii_letters + string.digits + "_-.")
print("🔍 Scanning for non-ASCII or invalid IDs...")

res = index.query(vector=[0]*3072, top_k=10000, include_metadata=False)
bad_ids = [v["id"] for v in res.get("matches", []) if any(c not in valid_chars for c in v["id"])]

if not bad_ids:
    print("✅ No invalid IDs found.")
else:
    index.delete(ids=bad_ids)
    print(f"🧹 Deleted {len(bad_ids)} invalid vector IDs.")
