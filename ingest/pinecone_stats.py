import os
from pinecone import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not PINECONE_API_KEY or not PINECONE_HOST:
    print("⚠ Pinecone stats skipped — missing env vars")
    exit(0)

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

stats = index.describe_index_stats()

print("\n📊 Pinecone Index Stats")
print("Namespaces:", stats.get("namespaces", {}))
print("Total vectors:", stats.get("total_vector_count", "unknown"))

