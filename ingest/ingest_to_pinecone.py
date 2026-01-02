#!/usr/bin/env python3
import os
import glob
import hashlib
from pinecone import Pinecone
from openai import OpenAI

# ---- ENV ----
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not PINECONE_API_KEY or not PINECONE_HOST:
    raise RuntimeError("Missing PINECONE_API_KEY or PINECONE_HOST")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

# ---- CONFIG ----
TRANSCRIPT_ROOT = "ingest/channels"
CHUNK_SIZE = 1200
NAMESPACE = "__default__"

# ---- CLIENTS ----
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

def stable_id(channel, text):
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{channel}|{h}"

def ingest():
    total_vectors = 0
    print("🔥 Starting Pinecone ingest")

    channel_dirs = sorted(glob.glob(f"{TRANSCRIPT_ROOT}/@*"))
    if not channel_dirs:
        print("⚠️ No channel directories found")
        return

    for channel_dir in channel_dirs:
        channel = os.path.basename(channel_dir)
        print(f"\n📘 Channel: {channel}")

        txt_files = sorted(glob.glob(f"{channel_dir}/*.txt"))
        if not txt_files:
            print("   ⚠️ No transcript files")
            continue

        for path in txt_files:
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

            index.upsert(vectors=vectors, namespace=NAMESPACE)
            total_vectors += len(vectors)

            print(f"   ✔ {os.path.basename(path)} → {len(vectors)} vectors")

    print(f"\n✅ Ingest complete — total vectors upserted: {total_vectors}")

if __name__ == "__main__":
    ingest()

