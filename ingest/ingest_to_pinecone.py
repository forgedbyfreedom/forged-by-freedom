#!/usr/bin/env python3
"""
🔥 Forged By Freedom — Quote-Level Pinecone Ingest
-------------------------------------------------
• Embeds sentence-aligned quote chunks
• Enforces podcast / speaker / episode attribution
• Uses OpenRouter embeddings
• Safe for large corpora (40M+ words)
"""

import os
import uuid
import json
import time
from pathlib import Path
from pinecone import Pinecone
import requests

# =====================
# ENVIRONMENT
# =====================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")
INDEX_NAME = "forged-freedom-ai"

EMBED_MODEL = "text-embedding-3-large"
MAX_CHUNK_TOKENS = 500
SLEEP_SECONDS = 0.4

assert OPENROUTER_API_KEY
assert PINECONE_API_KEY
assert PINECONE_HOST

# =====================
# INITIALIZE
# =====================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"

# =====================
# HELPERS
# =====================
def embed(text: str):
    res = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": EMBED_MODEL,
            "input": text
        },
        timeout=30
    )
    res.raise_for_status()
    return res.json()["data"][0]["embedding"]

def sentence_chunks(text):
    sentences = text.replace("\n", " ").split(". ")
    chunk = ""
    for s in sentences:
        if len(chunk) + len(s) < MAX_CHUNK_TOKENS * 4:
            chunk += s.strip() + ". "
        else:
            yield chunk.strip()
            chunk = s.strip() + ". "
    if chunk:
        yield chunk.strip()

# =====================
# INGEST
# =====================
total_chunks = 0

for channel_dir in TRANSCRIPTS_DIR.iterdir():
    if not channel_dir.is_dir():
        continue

    podcast = channel_dir.name.replace("@", "")

    for transcript_file in channel_dir.glob("master_transcript*.txt"):
        with open(transcript_file, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        episode = transcript_file.name
        for chunk in sentence_chunks(text):
            if len(chunk) < 200:
                continue

            vec = embed(chunk)

            index.upsert([{
                "id": str(uuid.uuid4()),
                "values": vec,
                "metadata": {
                    "podcast": podcast,
                    "speaker": podcast,
                    "episode": episode,
                    "quote": chunk
                }
            }])

            total_chunks += 1
            time.sleep(SLEEP_SECONDS)

        print(f"✅ Embedded {episode}")

print(f"\n🔥 Pinecone re-embed complete | chunks: {total_chunks}")
