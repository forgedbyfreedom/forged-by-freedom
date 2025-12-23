#!/usr/bin/env python3
"""
pinecone_index_upload.py
---------------------------------
Uploads all transcript text chunks into Pinecone with embeddings.

✅ Auto-creates Pinecone index if missing
✅ Splits transcripts into ~3500-token chunks
✅ Embeds via OpenAI (text-embedding-3-large)
✅ Uploads to Pinecone with metadata for search + summaries
"""

import os
import json
import tiktoken
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
from pathlib import Path
import os

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Optional sanity check (safe)
assert os.getenv("PINECONE_API_KEY"), "Missing PINECONE_API_KEY"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise SystemExit("❌ Missing OpenAI or Pinecone API key. Check .env file.")

# ============================================================
# ⚙️ Initialize Clients
# ============================================================
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Create index if it doesn’t exist
if INDEX_NAME not in pc.list_indexes().names():
    print(f"🪶 Creating Pinecone index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(INDEX_NAME)
print(f"✅ Connected to Pinecone index: {INDEX_NAME}")

# ============================================================
# 🧩 Helper: Chunk Text
# ============================================================
def chunk_text(text, max_tokens=3500):
    """Split large transcripts into smaller chunks."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    for i in range(0, len(tokens), max_tokens):
        yield enc.decode(tokens[i:i + max_tokens])

# ============================================================
# 🧠 Main Process
# ============================================================
TRANSCRIPTS_DIR = os.path.join(os.getcwd(), "transcripts")

print(f"📚 Scanning transcripts in: {TRANSCRIPTS_DIR}")

transcript_files = [
    os.path.join(root, file)
    for root, _, files in os.walk(TRANSCRIPTS_DIR)
    for file in files
    if file.endswith(".txt")
]

print(f"📁 Found {len(transcript_files)} transcript files to index.\n")

for file_path in transcript_files:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        if not text.strip():
            continue

        print(f"🧩 Chunking {file_path}...")
        chunks = list(chunk_text(text))
        print(f"➡️ Created {len(chunks)} chunks.")

        vectors = []
        for i, chunk in enumerate(chunks):
            embedding = client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk
            ).data[0].embedding

            vectors.append({
                "id": f"{os.path.basename(file_path)}_{i}",
                "values": embedding,
                "metadata": {
                    "source": os.path.basename(file_path),
                    "channel": os.path.basename(os.path.dirname(file_path)),
                    "chunk_index": i,
                    "text": chunk[:1500]  # preview text
                }
            })

        print(f"⬆️ Uploading {len(vectors)} vectors...")
        index.upsert(vectors)
        print(f"✅ Indexed {file_path} successfully!\n")

    except Exception as e:
        print(f"❌ Error indexing {file_path}: {e}")

print("🎯 All transcript indexing complete.")
