#!/usr/bin/env python3

import os
import hashlib
from pathlib import Path
import yaml

from pinecone import Pinecone
from openai import OpenAI

# =========================
# PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"
MANIFEST_PATH = BASE_DIR / "channel_manifest.yml"

CHUNK_SIZE = 1200
EMBED_MODEL = "text-embedding-3-large"
NAMESPACE = "__default__"

# =========================
# ENV
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not all([OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_HOST]):
    raise RuntimeError("❌ Missing required environment variables")

# =========================
# DEBUG
# =========================

print("🔍 INGEST STARTUP DEBUG")
print("• BASE_DIR:", BASE_DIR)
print("• CHANNELS_DIR exists:", CHANNELS_DIR.exists())
print("• Manifest exists:", MANIFEST_PATH.exists())
print("• Total .txt files:", len(list(CHANNELS_DIR.rglob("*.txt"))))

# =========================
# CLIENTS
# =========================

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)
client = OpenAI(api_key=OPENAI_API_KEY)

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
    for i in range(0, len(text), CHUNK_SIZE):
        yield text[i:i + CHUNK_SIZE]


def embed(texts):
    res = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]


def vector_id(category, channel, filename, chunk):
    h = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
    return f"{category}|{channel}|{filename}|{h}"

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

                vectors = []
                for chunk, emb in zip(chunks, embeddings):
                    vectors.append({
                        "id": vector_id(category_name, channel, txt.name, chunk),
                        "values": emb,
                        "metadata": {
                            "category": category_name,
                            "priority": priority,
                            "channel": channel,
                            "source": txt.name
                        }
                    })

                if vectors:
                    index.upsert(vectors=vectors, namespace=NAMESPACE)
                    total_vectors += len(vectors)

    print(f"\n✅ INGEST COMPLETE — total vectors: {total_vectors}")

# =========================
# ENTRY
# =========================

if __name__ == "__main__":
    ingest()

