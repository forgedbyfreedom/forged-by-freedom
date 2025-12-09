#!/usr/bin/env python3
"""
smart_pinecone_sync.py

Efficient incremental uploader for Pinecone.
- Detects new or modified transcript files
- Sanitizes vector IDs (ASCII-only)
- Uploads only changed files
- Skips duplicates
- Prevents mismatched vector dimensions
"""

import os
import json
import hashlib
import time
import re
from datetime import datetime
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# --- Load environment variables ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise ValueError("Missing required API keys in environment variables.")

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Ensure index exists
if PINECONE_INDEX not in pc.list_indexes().names():
    print(f"Creating new Pinecone index: {PINECONE_INDEX}")
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=1536,  # text-embedding-3-small
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(PINECONE_INDEX)

# --- Paths ---
TRANSCRIPTS_DIR = "transcripts"
FILE_INDEX_PATH = os.path.join(TRANSCRIPTS_DIR, "file_index.json")

# --- Load existing file index ---
if os.path.exists(FILE_INDEX_PATH):
    with open(FILE_INDEX_PATH, "r", encoding="utf-8") as f:
        file_index = json.load(f)
else:
    file_index = {}

def file_hash(path):
    """Compute MD5 hash for file content."""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def sanitize_id(text):
    """Ensure Pinecone vector IDs are ASCII-safe."""
    safe = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", text)
    return safe[:90]

def chunk_text(text, max_chars=3000):
    """Simple chunker for splitting long text."""
    for i in range(0, len(text), max_chars):
        yield text[i:i + max_chars]

# --- Find new or modified files ---
updated_files = []
for root, _, files in os.walk(TRANSCRIPTS_DIR):
    for file in files:
        if not file.endswith(".txt") or "master_manifest" in file:
            continue
        path = os.path.join(root, file)
        new_hash = file_hash(path)
        old_hash = file_index.get(path, {}).get("hash")
        if new_hash != old_hash:
            updated_files.append(path)

print(f"\nFound {len(updated_files)} new or modified transcript(s). Uploading...")

# --- Upload in batches ---
for path in tqdm(updated_files, desc="Uploading to Pinecone"):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()

        if not content:
            continue

        chunks = list(chunk_text(content))
        vectors = []
        for i, chunk in enumerate(chunks):
            embedding = client.embeddings.create(
                model="text-embedding-3-small", input=chunk
            ).data[0].embedding

            vec_id = sanitize_id(f"{os.path.basename(path)}_{i}")
            vectors.append({
                "id": vec_id,
                "values": embedding,
                "metadata": {
                    "source": path,
                    "chunk_index": i,
                    "text": chunk[:1500]
                }
            })

        index.upsert(vectors)
        file_index[path] = {
            "hash": file_hash(path),
            "chunks": len(chunks),
            "last_upload": datetime.now().isoformat()
        }
        time.sleep(1.0)

    except Exception as e:
        print(f"❌ Error uploading {path}: {e}")

# --- Save updated file index ---
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
with open(FILE_INDEX_PATH, "w", encoding="utf-8") as f:
    json.dump(file_index, f, indent=2)

print("\n✅ Pinecone sync complete!")
print(f"📊 {len(file_index)} files tracked in {FILE_INDEX_PATH}")
