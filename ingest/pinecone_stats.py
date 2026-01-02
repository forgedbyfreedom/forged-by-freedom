import os
import re
from pinecone import Pinecone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")

if not PINECONE_API_KEY or not PINECONE_INDEX:
    raise RuntimeError("Missing Pinecone environment variables")

NAMESPACE = "__default__"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

vector_count = 0
word_count = 0
episodes = set()

print("🔍 Scanning Pinecone namespace:", NAMESPACE)

for ids in index.list(namespace=NAMESPACE):
    fetched = index.fetch(ids=ids, namespace=NAMESPACE)

    for v in fetched.vectors.values():
        vector_count += 1
        meta = v.metadata or {}

        if "source" in meta:
            episodes.add(meta["source"])

        if "text" in meta:
            word_count += len(re.findall(r"\w+", meta["text"]))

print("\n📊 PINECONE INGEST STATS")
print("Vectors (chunks):", vector_count)
print("Episodes (unique sources):", len(episodes))
print("Estimated words:", word_count)

# Hard failure if Pinecone is empty (prevents silent regressions)
if vector_count == 0:
    raise RuntimeError("❌ Pinecone contains ZERO vectors — ingest failed")
