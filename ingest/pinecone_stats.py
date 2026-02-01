#!/usr/bin/env python3
"""
Forged By Freedom — Pinecone Stats
----------------------------------
Display index statistics and namespace breakdown.
"""

import os
from pinecone import Pinecone

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if not os.getenv("PINECONE_API_KEY"):
    raise RuntimeError("PINECONE_API_KEY not set")

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(INDEX_NAME)
stats = index.describe_index_stats()

print("\n┌─────────────────────────────────────────┐")
print("│       PINECONE INDEX STATS              │")
print("├─────────────────────────────────────────┤")
print(f"│  Index:     {INDEX_NAME:<26} │")
print(f"│  Dimension: {stats.get('dimension', 'N/A'):<26} │")
print(f"│  Total:     {stats.get('total_vector_count', 0):>20,} vectors │")
print("├─────────────────────────────────────────┤")

namespaces = stats.get("namespaces", {})
if namespaces:
    print("│  NAMESPACES                             │")
    for ns, data in sorted(namespaces.items()):
        count = data.get("vector_count", 0)
        name = ns if ns else "(default)"
        print(f"│    {name:<20} {count:>12,} │")
else:
    print("│  No namespaces found                    │")

print("└─────────────────────────────────────────┘\n")
