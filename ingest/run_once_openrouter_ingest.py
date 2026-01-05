#!/usr/bin/env python3

import os
import re
import hashlib
import time
from pathlib import Path
import yaml

from pinecone import Pinecone
from openai import OpenAI
from openai.error import APIError, RateLimitError

# =========================
# CONFIG
# =========================

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

EMBED_BATCH_SIZE = 32
EMBED_SLEEP = 0.3
EMBED_MAX_RETRIES = 5

UPSERT_BATCH_SIZE = 100
UPSERT_SLEEP = 0.1

EMBED_MODEL = "openai/text-embedding-3-large"
NAMESPACE = "__default__"

# =========================
# PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"
MANIFEST_PATH = BASE_DIR / "channel_manifest.yml"

# =========================
# ENV
# =========================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not OPENROUTER_API_KEY:
    raise RuntimeError("❌ OPENROUTER_API_KEY not set")

if not PINECONE_API_KEY or not PINECONE_HOST:
    raise RuntimeError("❌ Pinecone environment variables missing")

# =========================
# CLIENTS
# =========================

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://forged-by-freedom.local",
        "X-Title": "ForgedByFreedom Ingest"
    }
)

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

# =========================
# DEBUG
# =========================

print("🔍 INGEST STARTUP DEBUG")
print("• BASE_DIR:", BASE_DIR)
print("• CHANNELS_DIR exists:", CHANNELS_DIR.exists())
print("• Manifest exists:", MANIFEST_PATH.exists())
print("• Total .txt files:", len(list(CHANNELS_DIR.rglob("*.txt"))))
print("• Using base_url:", client.base_url)
print("• Embedding model:", EMBED_MODEL)

# =========================
# HELPERS
# =========================

def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    categories = manifest.get("categories")
    if not isinstance(categories, dict):
        raise RuntimeError("❌ categories must be a dict")

    return categories


def chunk_text(text):
    start = 0
    while start < len(text):
        yield text[start:start + CHUNK_SIZE]
        start += CHUNK_SIZE - CHUNK_OVERLAP


def embed_batch(batch):
    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        try:
            response = client.embeddings.create(
                model=EMBED_MODEL,
                input=batch
            )

            if not response.data:
                raise ValueError("Empty embedding response")

            return [item.embedding for item in response.data]

        except (ValueError, APIError, RateLimitError) as e:
            wait = attempt * 1.5
            print(f"⚠️ Embed retry {attempt}/{EMBED_MAX_RETRIES} after error: {e}")
            time.sleep(wait)

    print("❌ Failed embedding batch after retries — skipping batch")
    return []


def embed(texts):
    embeddings = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        batch_embeddings = embed_batch(batch)

        if len(batch_embeddings) != len(batch):
            print("⚠️ Batch size mismatch — skipping this batch")
            continue

        embeddings.extend(batch_embeddings)
        time.sleep(EMBED_SLEEP)

    return embeddings


def ascii_safe(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def vector_id(category, channel, filename, chunk, idx):
    base = f"{category}_{channel}_{filename}_{idx}"
    safe = ascii_safe(base)
    h = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:16]
    return f"{safe}_{h}"


def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]

# =========================
# INGEST
# =========================

def ingest():
    categories = load_manifest()
    total_vectors = 0

    print("🚀 BEGIN INGEST")

    for category_name, category in categories.items():
        priority = category.get("priority", 1)
        channels = category.get("channels", [])

        print(f"\n📂 CATEGORY: {category_name} (priority {priority})")

        for channel in channels:
            channel_path = CHANNELS_DIR / channel

            if not channel_path.exists():
                print(f"⚠️ Missing channel folder: {channel}")
                continue

            txt_files = list(channel_path.rglob("*.txt"))
            print(f"   ├─ {channel}: {len(txt_files)} files")

            for txt in txt_files:
                text = txt.read_text(encoding="utf-8", errors="ignore").strip()
                if not text:
                    continue

                chunks = list(chunk_text(text))
                embeddings = embed(chunks)

                if not embeddings:
                    print(f"⚠️ No embeddings for file {txt.name} — skipping")
                    continue

                vectors = []
                for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    vectors.append({
                        "id": vector_id(category_name, channel, txt.name, chunk, idx),
                        "values": emb,
                        "metadata": {
                            "category": category_name,
                            "priority": priority,
                            "channel": channel,
                            "source": txt.name
                        }
                    })

                for batch in batched(vectors, UPSERT_BATCH_SIZE):
                    index.upsert(vectors=batch, namespace=NAMESPACE)
                    total_vectors += len(batch)
                    time.sleep(UPSERT_SLEEP)

    print(f"\n✅ INGEST COMPLETE — total vectors: {total_vectors}")

# =========================
# ENTRY
# =========================

if __name__ == "__main__":
    ingest()
