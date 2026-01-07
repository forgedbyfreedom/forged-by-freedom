#!/usr/bin/env python3
import os
import hashlib
from pathlib import Path
import yaml
import time

from pinecone import Pinecone
from openai import OpenAI

# =========================
# CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"
MANIFEST_PATH = BASE_DIR / "channel_manifest.yml"

INDEX_NAME = os.getenv("PINECONE_INDEX", "forged-freedom-ai")
NAMESPACE = "default"

EMBED_MODEL = "text-embedding-3-large"
CHUNK_SIZE = 1200
MAX_UPSERT_BATCH = 100

CHECKPOINT_FILE = BASE_DIR / ".completed_files.txt"

# =========================
# ENV VALIDATION
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY not set")

if not PINECONE_API_KEY:
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# =========================
# CLIENTS
# =========================

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

# =========================
# DEBUG
# =========================

print("🔍 INGEST STARTUP DEBUG")
print("• BASE_DIR:", BASE_DIR)
print("• CHANNELS_DIR exists:", CHANNELS_DIR.exists())
print("• Manifest exists:", MANIFEST_PATH.exists())
print("• Total .txt files:", len(list(CHANNELS_DIR.rglob("*.txt"))))
print("• Pinecone index:", INDEX_NAME)
print("• Embedding model:", EMBED_MODEL)

# =========================
# HELPERS
# =========================

def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("categories", {})

def load_completed():
    if not CHECKPOINT_FILE.exists():
        return set()
    return set(CHECKPOINT_FILE.read_text().splitlines())

def mark_completed(path: str):
    with open(CHECKPOINT_FILE, "a") as f:
        f.write(path + "\n")

def chunk_text(text: str):
    for i in range(0, len(text), CHUNK_SIZE):
        yield text[i:i + CHUNK_SIZE], i // CHUNK_SIZE

def make_vector_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def embed(texts):
    res = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]

# =========================
# INGEST
# =========================

def ingest():
    categories = load_manifest()
    completed = load_completed()

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
                file_key = str(txt.resolve())

                if file_key in completed:
                    continue

                text = txt.read_text(encoding="utf-8", errors="ignore").strip()
                if not text:
                    mark_completed(file_key)
                    continue

                chunks = list(chunk_text(text))
                texts = [c[0] for c in chunks]

                try:
                    embeddings = embed(texts)
                except Exception as e:
                    print(f"❌ Embed failed: {txt.name} — {e}")
                    continue

                vectors = []
                for (chunk_text_val, chunk_index), embedding in zip(chunks, embeddings):
                    vector_id = make_vector_id(
                        category_name,
                        channel,
                        txt.name,
                        str(chunk_index)
                    )

                    vectors.append({
                        "id": vector_id,
                        "values": embedding,
                        "metadata": {
                            "category": category_name,
                            "priority": priority,
                            "channel": channel,
                            "source": txt.name,
                            "chunk": chunk_index
                        }
                    })

                for i in range(0, len(vectors), MAX_UPSERT_BATCH):
                    batch = vectors[i:i + MAX_UPSERT_BATCH]
                    index.upsert(vectors=batch, namespace=NAMESPACE)
                    time.sleep(0.2)

                mark_completed(file_key)

    print("\n✅ INGEST COMPLETE")

# =========================
# ENTRY
# =========================

if __name__ == "__main__":
    ingest()
