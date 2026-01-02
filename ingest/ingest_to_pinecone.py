#!/usr/bin/env python3

import os
import glob
import hashlib
from pinecone import Pinecone
from openai import OpenAI

# ---- ENV ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")
if not PINECONE_API_KEY:
    raise RuntimeError("Missing PINECONE_API_KEY")
if not PINECONE_HOST:
    raise RuntimeError("Missing PINECONE_HOST (required for serverless Pinecone)")

# ---- CONFIG ----
TRANSCRIPT_ROOT = "ingest/channels"
CHUNK_SIZE = 1200
NAMESPACE = "__default__"
EMBED_MODEL = "text-embedding-3-large"

# ---- CLIENTS ----
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)
client = OpenAI(api_key=OPENAI_API_KEY)

def chunk_text(text):
    for i in range(0, len(text), CHUNK_SIZE):
        yield text[i:i + CHUNK_SIZE]

def stable_id(channel, content):
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{channel}|{h}"

def embed(texts):
    res = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]

def ingest():
    total_vectors = 0
    print("🔥 Starting Pinecone ingest")

    for channel_dir in sorted(glob.glob(f"{TRANSCRIPT_ROOT}/@*")):
        channel = os.path.basename(channel_dir)
        print(f"\n📘 Channel: {channel}")

        for path in sorted(glob.glob(f"{channel_dir}/*.txt")):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()

            if not text:
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

            if vectors:
                index.upsert(vectors=vectors, namespace=NAMESPACE)
                total_vectors += len(vectors)
                print(f"   ✔ {os.path.basename(path)} → {len(vectors)} vectors")

    print(f"\n✅ Ingest complete — total vectors upserted: {total_vectors}")

if __name__ == "__main__":
    ingest()

