#!/usr/bin/env python3

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

MAX_CHARS = 1200           # smaller = safer
BATCH_SIZE = 25            # Pinecone safe
RETRY_LIMIT = 5
RETRY_SLEEP = 4            # seconds

OPENROUTER_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1/embeddings"
)

EMBED_MODEL = os.getenv(
    "OPENROUTER_EMBED_MODEL",
    "text-embedding-3-large"
)

# ==============================
# ENV CHECK
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
# CLIENTS
# ==============================

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

HEADERS = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
    "Content-Type": "application/json",
    "User-Agent": "forged-by-freedom-ingest/1.0",
}

# ==============================
# HELPERS
# ==============================

def chunk_text(text: str) -> List[str]:
    return [
        text[i:i + MAX_CHARS]
        for i in range(0, len(text), MAX_CHARS)
    ]


def embed_texts(texts: List[str]) -> List[List[float]]:
    payload = {
        "model": EMBED_MODEL,
        "input": texts,
    }

    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            r = requests.post(
                OPENROUTER_URL,
                headers=HEADERS,
                json=payload,
                timeout=60,
            )

            if r.status_code != 200:
                print(f"⚠️ OpenRouter HTTP {r.status_code}")
                print(r.text[:500])
                raise RuntimeError("Non-200 response")

            try:
                data = r.json()
            except Exception:
                print("⚠️ OpenRouter returned non-JSON:")
                print(r.text[:500])
                raise

            return [item["embedding"] for item in data["data"]]

        except Exception as e:
            print(f"🔁 Embed retry {attempt}/{RETRY_LIMIT}: {e}")
            time.sleep(RETRY_SLEEP * attempt)

    raise RuntimeError("❌ Embedding failed after retries")


def upsert_safe(vectors: List[Dict]):
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        index.upsert(vectors=batch)
        print(f"   ✅ Upserted {i + len(batch)} / {len(vectors)}")
        time.sleep(0.3)

# ==============================
# MAIN
# ==============================

def run():
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

        try:
            embeddings = embed_texts(chunks)
        except Exception as e:
            print(f"❌ Failed embeddings for {file.name}: {e}")
            continue

        for chunk, embedding in zip(chunks, embeddings):
            buffer.append({
                "id": str(uuid.uuid4()),
                "values": embedding,
                "metadata": {
                    "source": str(file),
                    "filename": file.name,
                    "text": chunk[:700],
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
