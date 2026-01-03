#!/usr/bin/env python3
import os
from pinecone import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST    = os.getenv("PINECONE_HOST")

if not PINECONE_API_KEY or not PINECONE_HOST:
    raise RuntimeError("Missing Pinecone environment variables (PINECONE_API_KEY, PINECONE_HOST)")

PINECONE_HOST = PINECONE_HOST.strip()

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

stats = index.describe_index_stats()

print("\n📊 Pinecone Index Stats")
namespaces = list((stats.get("namespaces") or {}).keys())
print("Namespaces:", namespaces)

ns = "__default__"
vec_count = (stats.get("namespaces") or {}).get(ns, {}).get("vector_count", 0)
print(f"Vector count ({ns}): {vec_count}")

