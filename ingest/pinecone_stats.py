#!/usr/bin/env python3
import os
from pinecone import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not PINECONE_API_KEY or not PINECONE_HOST:
    raise RuntimeError("Missing Pinecone environment variables")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

stats = index.describe_index_stats()

print("\n📊 Pinecone Index Stats")
print(f"Namespaces: {list(stats.namespaces.keys())}")

ns = stats.namespaces.get("__default__", {})
print(f"Vector count (__default__): {ns.get('vector_count', 0)}")

