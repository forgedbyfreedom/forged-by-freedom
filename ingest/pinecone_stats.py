import os
from pinecone import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not all([PINECONE_API_KEY, PINECONE_HOST]):
    raise RuntimeError("Missing Pinecone environment variables")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

stats = index.describe_index_stats()

print("\n📊 Pinecone Index Stats")
print("Namespaces:", stats.get("namespaces", {}))
print("Total vector count:", stats.get("total_vector_count"))

