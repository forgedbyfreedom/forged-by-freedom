#!/usr/bin/env python3

import os
import glob
import hashlib
from pinecone import Pinecone
from openai import OpenAI

# ENV
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([PINECONE_API_KEY, PINECONE_HOST, OPENAI_API_KEY]):
    raise RuntimeError("Missing required environment variables")

TRANSCRIPT_ROOT = "ingest/channels"
CHUNK_SIZE = 1200
NAMESPACE = "__default__"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)
client = OpenAI(api_key=OPENAI_API_KEY)

def chunk_text(text):
    for i in range(0, len(text), CHUNK_SIZE):
        yield text[i:i + CHUNK_SIZE]

def embed(texts):
    res = client.embeddings.create(
        model="text-embedding-3-large",
        input=texts
    )
    return [d.embedding for d in res.data]

def stable_id(channel, content):
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{channel}|{h}"

def ingest():
    print("🔥 Starting Pinecone ingest")

    channel_dirs = sorted(glob.glob(f"{TRANSCRIPT_ROOT}/@*"))
    if not channel_dirs:
        print("⚠️ No channel directories found")
        return

    total_vectors = 0

    for channel_dir in channel_dirs:
        channel = os.path.basename(channel_dir)
        print(f"\n📘 Channel: {channel}")

        for path in sorted(glob.glob(f"{channel_dir}/*.txt")):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            chunks = list(chunk_text(text))
            if not chunks:
                continue

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

