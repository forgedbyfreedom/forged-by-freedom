#!/usr/bin/env python3

import os
import glob
import hashlib
from pinecone import Pinecone
from openai import OpenAI

# =========================
# REQUIRED ENV VARS
# =========================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not PINECONE_API_KEY:
    raise RuntimeError("Missing PINECONE_API_KEY")

if not PINECONE_HOST:
    raise RuntimeError("Missing PINECONE_HOST")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

# =========================
# CONFIG
# =========================
TRANSCRIPT_ROOT = "ingest/channels"   # <-- THIS MUST EXIST
CHUNK_SIZE = 1200
NAMESPACE = "__default__"

# =========================
# CLIENTS
# =========================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)
client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# HELPERS
# =========================
def chunk_text(text, size=CHUNK_SIZE):
    for i in range(0, len(text), size):
        yield text[i:i + size]

def embed(texts):
    res = client.embeddings.create(
        model="text-embedding-3-large",
        input=texts
    )
    return [r.embedding for r in res.data]

def stable_id(channel, text):
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{channel}-{h}"

# =========================
# INGEST
# =========================
def ingest():
    print("🔥 Starting Pinecone ingest")

    if not os.path.isdir(TRANSCRIPT_ROOT):
        raise RuntimeError(f"Transcript root not found: {TRANSCRIPT_ROOT}")

    total_vectors = 0

    for channel_dir in sorted(glob.glob(f"{TRANSCRIPT_ROOT}/@*")):
        channel = os.path.basename(channel_dir)
        print(f"\n📘 Channel: {channel}")

        txt_files = sorted(glob.glob(f"{channel_dir}/*.txt"))
        if not txt_files:
            print("   ⚠️ No transcript files found")
            continue

        for path in txt_files:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()

            if not text:
                print(f"   ⚠️ Empty file skipped: {os.path.basename(path)}")
                continue

            chunks = list(chunk_text(text))
            embeddings = embed(chunks)

            vectors = []
            for chunk, emb in zip(chunks, embeddings):
                vectors.append({
                    "id": stable_id(channel, chunk),
                    "values": emb,
                    "metadata": {
                        "channel": channel,
                        "source": os.path.basename(path)
                    }
                })

            index.upsert(vectors=vectors, namespace=NAMESPACE)
            total_vectors += len(vectors)

            print(f"   ✔ {os.path.basename(path)} → {len(vectors)} vectors")

    print(f"\n✅ Ingest complete — total vectors upserted: {total_vectors}")

if __name__ == "__main__":
    ingest()
