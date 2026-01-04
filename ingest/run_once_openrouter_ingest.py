#!/usr/bin/env python3
"""
ONE-TIME INGEST SCRIPT
• Reads all .txt transcripts
• Embeds via OpenRouter
• Upserts to Pinecone (SDK v6+ compatible)
• Safe batching to avoid 2MB limit
"""

import os
import sys
import time
import uuid
from pathlib import Path
from typing import List, Dict

import requests
from pinecone import Pinecone

# ==============================
# CONFIG
# ==============================

BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"

BATCH_SIZE = 40          # conservative for 2MB limit
MAX_CHARS = 1500

OPENROUTER_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1/embeddings"
)

EMBED_MODEL = os.getenv(
    "OPENROUTER_EMBED_MODEL",
    "text-embedding-3-large"
)

# ==============================
# ENV VALIDATION
# ==============================

REQUIRED = [
    "OPENROUTER_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX_NAME",
]

for var in REQUIRED:
    if not os.getenv(var):
        print(f"❌ Missing env var: {var}")
        sys.exit(1)

print("✅ Environment variables verified")

# ==============================
# INIT CLIENTS (NEW SDK)
# ==============================

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

HEADERS = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
    "Content-Type": "application/json",
}

# ==============================
# HELPERS
# ==============================

def chunk_text(text: str, max_chars: int = MAX_CHARS) -> List[str]:
    return [
        text[i:i + max_chars]
        for i in range(0, len(text), max_chars)
    ]


def embed_texts(texts: List[str]) -> List[List[float]]:
    payload = {
        "model": EMBED_MODEL,
        "input": texts,
    }

    r = requests.post(
        OPENROUTER_URL,
        headers=HEADERS,
        json=payload,
        timeout=60
    )
    r.raise_for_status()
    data = r.json()

    return [item["embedding"] for item in data["data"]]


def upsert_safe(vectors: List[Dict]):
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        index.upsert(vectors=batch)
        print(f"   ✅ Upserted {i + len(batch)} / {len(vectors)}")
        time.sleep(0.25)


# ==============================
# MAIN
# ==============================

def run():
    print(f"📂 Scanning transcripts in: {CHANNELS_DIR}")

    files = list(CHANNELS_DIR.rglob("*.txt"))
    print(f"📄 Found {len(files)} transcript files")

    buffer = []

    for file in files:
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"⚠️ Skipped unreadable file: {file} ({e})")
            continue

        chunks = chunk_text(text)
        print(f"➡️ {file.name}: {len(chunks)} chunks")

        embeddings = embed_texts(chunks)

        for chunk, embedding in zip(chunks, embeddings):
            buffer.append({
                "id": str(uuid.uuid4()),
                "values": embedding,
                "metadata": {
                    "source": str(file),
                    "filename": file.name,
                    "text": chunk[:800],
                },
            })

        if len(buffer) >= BATCH_SIZE:
            print(f"⬆️ Upserting batch ({len(buffer)})")
            upsert_safe(buffer)
            buffer.clear()

    if buffer:
        print(f"⬆️ Final upsert ({len(buffer)})")
        upsert_safe(buffer)

    print("🎉 INGEST COMPLETE")


# ==============================
# ENTRY
# ==============================

if __name__ == "__main__":
    print("🚀 STARTING OPENROUTER → PINECONE INGEST")
    run()
