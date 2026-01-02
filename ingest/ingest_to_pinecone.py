#!/usr/bin/env python3
"""
Forged By Freedom — GitHub → Pinecone Ingest
-------------------------------------------
• Reads per-channel transcripts
• Chunks text
• Creates embeddings
• Upserts to Pinecone (incremental, id-stable)
"""

import os
import glob
import hashlib
from pinecone import Pinecone
from openai import OpenAI

# ENV VARS (from GitHub Secrets)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TRANSCRIPT_ROOT = "ingest/channels"
CHUNK_SIZE = 1200

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)
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

    for channel_dir in sorted(glob.glob(f"{TRANSCRIPT_ROOT}/@*")):
        channel = os.path.basename(channel_dir)
        print(f"\n📘 Channel: {channel}")

        for path in sorted(glob.glob(f"{channel_dir}/*.txt")):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            chunks = list(chunk_text(text))
            embeddings = embed(chunks)

            vectors = []
            for chunk, emb in zip(chunks, embeddings):
                vid = stable_id(channel, chunk)
                vectors.append({
                    "id": vid,
                    "values": emb,
                    "metadata": {
                        "channel": channel,
                        "source": os.path.basename(path)
                    }
                })

            index.upsert(vectors=vectors, namespace="__default__")
            print(f"   ✔ {os.path.basename(path)} → {len(vectors)} vectors")

    print("\n✅ Ingest complete")

if __name__ == "__main__":
    ingest()
