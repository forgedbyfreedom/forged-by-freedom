#!/usr/bin/env python3
"""
Forged By Freedom — GitHub → Pinecone Ingest (SERVERLESS SAFE)
------------------------------------------------------------
• Reads per-channel transcripts
• Chunks text
• Creates embeddings
• Upserts to Pinecone (__default__ namespace)
• Host-only (no Pinecone discovery calls)
"""

import os
import glob
import hashlib
from pinecone import Pinecone
from openai import OpenAI

# ─────────────────────────────
# REQUIRED ENV VARS (GitHub Secrets)
# ─────────────────────────────
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not PINECONE_API_KEY:
    raise RuntimeError("Missing PINECONE_API_KEY")
if not PINECONE_HOST:
    raise RuntimeError("Missing PINECONE_HOST (required for serverless Pinecone)")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
TRANSCRIPT_ROOT = "ingest/channels"
CHUNK_SIZE = 1200
NAMESPACE = "__default__"

# ─────────────────────────────
# CLIENTS
# ─────────────────────────────
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)
client = OpenAI(api_key=OPENAI_API_KEY)

print(f"✔ Connected to Pinecone host: {PINECONE_HOST}")

# ─────────────────────────────
# HELPERS
# ─────────────────────────────
def chunk_text(text, size):
    for i in range(0, len(text), size):
        yield text[i:i + size]

def embed_texts(texts):
    res = client.embeddings.create(
        model="text-embedding-3-large",
        input=texts
    )
    return [d.embedding for d in res.data]

def stable_id(channel, source, content):
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{channel}|{source}|{h}"

# ─────────────────────────────
# INGEST
# ─────────────────────────────
def ingest():
    print("\n🔥 Starting Pinecone ingest\n")

    total_vectors = 0

    for channel_dir in sorted(glob.glob(f"{TRANSCRIPT_ROOT}/@*")):
        channel = os.path.basename(channel_dir)
        print(f"📘 Channel: {channel}")

        for path in sorted(glob.glob(f"{channel_dir}/*.txt")):
            source = os.path.basename(path)

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()

            if not text:
                print(f"   ⚠ {source} skipped (empty)")
                continue

            chunks = list(chunk_text(text, CHUNK_SIZE))
            embeddings = embed_texts(chunks)

            vectors = []
            for chunk, emb in zip(chunks, embeddings):
                vid = stable_id(channel, source, chunk)
                vectors.append({
                    "id": vid,
                    "values": emb,
                    "metadata": {
                        "channel": channel,
                        "source": source,
                        "text": chunk
                    }
                })

            index.upsert(vectors=vectors, namespace=NAMESPACE)
            total_vectors += len(vectors)

            print(f"   ✔ {source} → {len(vectors)} vectors")

    print(f"\n✅ Ingest complete — total vectors upserted: {total_vectors}")

# ─────────────────────────────
# ENTRYPOINT
# ─────────────────────────────
if __name__ == "__main__":
    ingest()
