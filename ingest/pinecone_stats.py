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

print("\n📊 PINECONE INDEX STATS")
print(f"Namespaces: {list(stats['namespaces'].keys())}")

total = 0
for ns, data in stats["namespaces"].items():
    count = data["vector_count"]
    print(f"  • {ns or 'default'}: {count} vectors")
    total += count

print(f"\n✅ TOTAL VECTORS: {total}")

