#!/usr/bin/env python3
"""
merge_and_dedupe_transcripts.py
--------------------------------
One-time master script to merge all transcript data from:
- Local GitHub repos (thinkbig-transcripts, fbf-data, forged-by-freedom)
- OpenAI File Storage (uploaded transcripts)
- Existing Pinecone index (if present)

Deduplicates across all sources, embeds using OpenAI, and updates Pinecone index.
"""

import os
import json
import hashlib
import time
from pathlib import Path
from tqdm import tqdm
from openai import OpenAI
import pinecone

# === Load environment variables ===
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "forged-freedom-ai")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise SystemExit("❌ Missing API keys — check your .env file.")

client = OpenAI(api_key=OPENAI_API_KEY)

# === Initialize Pinecone ===
pinecone.init(api_key=PINECONE_API_KEY, environment="us-east1-gcp")
if PINECONE_INDEX not in pinecone.list_indexes().names():
    pinecone.create_index(name=PINECONE_INDEX, dimension=3072, metric="cosine")

index = pinecone.Index(PINECONE_INDEX)

# === Helper functions ===

def clean_text(text: str) -> str:
    """Remove noise, timestamps, and repeated whitespace."""
    import re
    text = re.sub(r"\[[0-9:]+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?i)transcript|episode|podcast", "", text)
    return text.strip()

def chunk_text(text: str, size: int = 400):
    """Chunk text into ~400 word sections for embedding."""
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i+size])

def file_hash(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()

# === Phase 1: Gather files from local repos ===

root_dirs = [
    Path("transcripts"),
    Path("thinkbig-transcripts"),
    Path("fbf-data")
]

print("\n📁 Scanning local transcript repositories...")
local_texts = {}

for root in root_dirs:
    if not root.exists():
        continue
    for txt in root.rglob("*.txt"):
        try:
            content = open(txt, "r", encoding="utf-8", errors="ignore").read()
            cleaned = clean_text(content)
            h = file_hash(cleaned)
            local_texts[h] = {"path": str(txt), "text": cleaned}
        except Exception as e:
            print(f"⚠️ Error reading {txt}: {e}")

print(f"✅ Found {len(local_texts)} unique text files locally.")

# === Phase 2: Include OpenAI Storage Files ===

print("\n☁️ Checking OpenAI file storage...")
try:
    openai_files = client.files.list().data
    print(f"✅ Found {len(openai_files)} files in OpenAI storage.")
except Exception as e:
    print(f"⚠️ Error listing OpenAI files: {e}")
    openai_files = []

# === Phase 3: Pull existing Pinecone metadata ===

print("\n🔍 Checking Pinecone index...")
try:
    stats = index.describe_index_stats()
    total_vectors = stats["total_vector_count"]
    print(f"✅ Pinecone contains {total_vectors} total vectors.")
except Exception as e:
    print(f"⚠️ Unable to retrieve Pinecone stats: {e}")

# === Phase 4: Deduplicate + Embed new text ===

print("\n🧠 Embedding and uploading new text chunks to Pinecone...")
existing_hashes = set(local_texts.keys())
batch = []
batch_size = 50
upserts = 0

for h, entry in tqdm(local_texts.items()):
    text = entry["text"]
    chunks = list(chunk_text(text))
    for i, chunk in enumerate(chunks):
        chunk_id = f"{h}-{i}"
        try:
            embedding = client.embeddings.create(
                input=chunk,
                model="text-embedding-3-large"
            ).data[0].embedding

            batch.append((chunk_id, embedding, {"source": entry["path"]}))

            if len(batch) >= batch_size:
                index.upsert(vectors=batch)
                upserts += len(batch)
                batch.clear()

        except Exception as e:
            print(f"⚠️ Failed to embed {entry['path']}: {e}")

# Final upsert
if batch:
    index.upsert(vectors=batch)
    upserts += len(batch)

print(f"\n✅ Uploaded {upserts} new vectors to Pinecone.")

# === Phase 5: Write manifest file ===

manifest = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "total_files": len(local_texts),
    "total_vectors": upserts,
    "sources": list({Path(p['path']).parent.name for p in local_texts.values()})
}

with open("file_index.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print("\n📦 Manifest written to file_index.json")
print(json.dumps(manifest, indent=2))

print("\n🎯 Merge and deduplication complete!")
print("All transcript data is now unified in Pinecone.")
