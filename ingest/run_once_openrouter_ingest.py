#!/usr/bin/env python3
"""
One-time ingest script:
• Reads ALL .txt transcripts
• Embeds via OpenRouter
• Upserts to Pinecone in SAFE batches (<= 2MB)
"""

import os
import sys
import time
import uuid
from pathlib import Path
from typing import List, Dict

import pinecone
import requests

# ==============================
# CONFIG
# ==============================

BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"

BATCH_SIZE = 50                 # SAFE Pinecone batch size
EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")
OPENROUTER_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/embeddings")

# ==============================
# ENV VALIDATION
# ==============================

REQUIRED_ENVS = [
    "OPENROUTER_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX_NAME",
]

for env in REQUIRED_ENVS:
    if not os.getenv(env):
        print(f"❌ Missing env var: {env}")
        sys.exit(1)

print("✅ Environment variables verified")

# ==============================
# INIT CLIENTS
# ==============================

pinecone.init(api_key=os.getenv("PINECONE_API_KEY"))
index = pinecone.Index(os.getenv("PINECONE_INDEX_NAME"))

HEADERS = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
    "Content-Type": "application/json",
}

# ==============================
# HELPERS
# ==============================

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Call OpenRouter embedding API"""
    payload = {
        "model": EMBED_MODEL,
        "input": texts,
    }

    r = requests.post(OPENROUTER_URL, headers=HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    return [d["embedding"] for d in data["data"]]


def chunk_text(text: str, max_chars: int = 1500) -> List[str]:
    """Split long transcript into manageable chunks"""
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + max_chars])
        start += max_chars
    return chunks


# ==============================
# MAIN INGEST
# ==============================

def run():
    print(f"📂 Scanning transcripts in: {CHANNELS_DIR}")

    txt_files = list(CHANNELS_DIR.rglob("*.txt"))
    print(f"📄 Found {len(txt_files)} transcript files")

    vectors = []

    for file_path in txt_files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"⚠️ Skipping unreadable file: {file_path} ({e})")
            continue

        chunks = chunk_text(text)

        print(f"➡️ {file_path.name}: {len(chunks)} chunks")

        embeddings = embed_texts(chunks)

        for chunk, embedding in zip(chunks, embeddings):
            vectors.append({
                "id": str(uuid.uuid4()),
                "values": embedding,
                "metadata": {
                    "source": str(file_path),
                    "filename": file_path.name,
                    "text": chunk[:1000],   # keep metadata small
                },
            })

        # ------------------------------
        # SAFE UPSERT IN BATCHES
        # ------------------------------
        if len(vectors) >= BATCH_SIZE:
            flush_vectors(vectors)
            vectors.clear()

    # Final flush
    if vectors:
        flush_vectors(vectors)

    print("🎉 INGEST COMPLETE")


def flush_vectors(vectors: List[Dict]):
    total = len(vectors)
    print(f"⬆️ Upserting {total} vectors to Pinecone")

    for i in range(0, total, BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        index.upsert(vectors=batch)
        print(f"   ✅ Upserted {min(i + BATCH_SIZE, total)}/{total}")
        time.sleep(0.2)  # light throttle


# ==============================
# ENTRY
# ==============================

if __name__ == "__main__":
    print("🚀 STARTING ONE-TIME OPENROUTER → PINECONE INGEST")
    run()
