#!/usr/bin/env python3
"""
merge_and_dedupe_transcripts.py
--------------------------------
One-time master script to merge local transcripts, dedupe, embed, and upsert to Pinecone.

NOTE:
- Uses OpenRouter embeddings (via OpenAI SDK base_url OR direct HTTP)
- Uses Pinecone SDK (Pinecone class), NOT pinecone.init()
"""

import os
import json
import hashlib
import time
from pathlib import Path

from tqdm import tqdm
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI


# ---- ENV (explicit path) ----
ROOT = Path(__file__).resolve().parents[2]  # .github/scripts -> repo root
load_dotenv(dotenv_path=ROOT / ".env", override=True)

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()

if not OPENROUTER_API_KEY or not PINECONE_API_KEY:
    raise SystemExit("❌ Missing OPENROUTER_API_KEY or PINECONE_API_KEY")

or_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)


def clean_text(text: str) -> str:
    import re
    text = re.sub(r"\[[0-9:]+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, size_words: int = 400):
    words = text.split()
    for i in range(0, len(words), size_words):
        yield " ".join(words[i:i+size_words])


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", "surrogatepass")).hexdigest()


def embed(chunk: str):
    resp = or_client.embeddings.create(model=EMBED_MODEL, input=chunk)
    return resp.data[0].embedding


# ---- gather files ----
root_dirs = [
    ROOT / "transcripts_all",
    ROOT / "transcripts",
    ROOT / "split_transcripts",
]

print("\n📁 Scanning transcript directories...")
unique_texts = {}

for base in root_dirs:
    if not base.exists():
        continue
    for txt in base.rglob("*.txt"):
        try:
            raw = txt.read_text(encoding="utf-8", errors="ignore")
            cleaned = clean_text(raw)
            if len(cleaned) < 200:
                continue
            h = sha1(cleaned)
            if h not in unique_texts:
                unique_texts[h] = {"path": str(txt.relative_to(ROOT)), "text": cleaned}
        except Exception as e:
            print(f"⚠️ Error reading {txt}: {e}")

print(f"✅ Found {len(unique_texts)} unique transcript files")

# ---- embed + upsert ----
print("\n🧠 Embedding and uploading chunks to Pinecone...")
batch = []
BATCH_SIZE = 50
upserts = 0

for h, entry in tqdm(unique_texts.items(), desc="Upserting"):
    chunks = list(chunk_text(entry["text"]))
    for i, chunk in enumerate(chunks):
        vec_id = f"{h}-{i}"
        try:
            emb = embed(chunk)
            batch.append({
                "id": vec_id,
                "values": emb,
                "metadata": {
                    "source": entry["path"],
                    "hash": h,
                    "chunk": i,
                    "text": chunk[:2000],
                }
            })

            if len(batch) >= BATCH_SIZE:
                index.upsert(vectors=batch)
                upserts += len(batch)
                batch.clear()

        except Exception as e:
            print(f"⚠️ Failed to embed/upsert {entry['path']}: {e}")

if batch:
    index.upsert(vectors=batch)
    upserts += len(batch)

print(f"\n✅ Uploaded {upserts} vectors to Pinecone")

manifest = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "unique_files": len(unique_texts),
    "vectors_upserted": upserts,
}

out = ROOT / "file_index.json"
out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"📦 Manifest written: {out}")
print("🎯 Merge + dedupe complete.")
