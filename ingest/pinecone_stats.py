import os
from pinecone import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not PINECONE_API_KEY or not PINECONE_HOST:
    raise RuntimeError("Missing Pinecone environment variables")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

stats = index.describe_index_stats()

print("\n📊 PINECONE INDEX STATS")
print("Namespace counts:")
for ns, data in stats.get("namespaces", {}).items():
    print(f"  {ns}: {data.get('vector_count', 0)} vectors")

print("\nTotal vectors:", stats.get("total_vector_count", 0))

