import os
import re
from pinecone import Pinecone

# ─────────────────────────────
# ENV VARS REQUIRED
# ─────────────────────────────
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")

NAMESPACE = "__default__"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

vector_count = 0
word_count = 0
episodes = set()

# ─────────────────────────────
# Pinecone scan (pagination)
# ─────────────────────────────
print("Scanning Pinecone namespace:", NAMESPACE)

for ids in index.list(namespace=NAMESPACE):
    # list() returns batches of IDs
    fetched = index.fetch(ids=ids, namespace=NAMESPACE)
    vectors = fetched.vectors

    for v in vectors.values():
        vector_count += 1

        meta = v.metadata or {}

        # Episode / source tracking
        if "source" in meta:
            episodes.add(meta["source"])

        # Word count (ONLY if text stored)
        if "text" in meta:
            word_count += len(re.findall(r"\w+", meta["text"]))

print("\n── PINECONE STATS ──")
print("vectors (chunks):", vector_count)
print("episodes (unique sources):", len(episodes))
print("estimated words:", word_count)
