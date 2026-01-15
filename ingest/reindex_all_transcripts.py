#!/usr/bin/env python3
"""
🔥 GLOBAL REINDEX — FORGED BY FREEDOM
------------------------------------
• Reindexes ALL transcripts
• No redownload
• No reinjest
• Clean chunking
• Clean metadata
• One consistent Pinecone schema
"""

import os
import time
import hashlib
from pathlib import Path
import requests
from pinecone import Pinecone

# =======================
# ENV
# =======================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY missing")
if not PINECONE_API_KEY:
    raise RuntimeError("PINECONE_API_KEY missing")
if not PINECONE_HOST:
    raise RuntimeError("PINECONE_HOST missing")

INDEX_NAME = "forged-freedom-ai"
EMBED_MODEL = "text-embedding-3-large"
TRANSCRIPTS_DIR = Path("transcripts")

# =======================
# HELPERS
# =======================
def stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def chunk_text(text, max_chars=800):
    chunks = []
    buf = ""

    for sentence in text.split("."):
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(buf) + len(sentence) > max_chars:
            chunks.append(buf.strip())
            buf = ""

        buf += sentence + ". "

    if buf.strip():
        chunks.append(buf.strip())

    return chunks

def infer_audience(text):
    female_terms = ["women", "female", "girl", "viril", "menstrual", "clit", "voice"]
    if any(t in text for t in female_terms):
        return "female"
    return "general"

def infer_topic(text):
    if "tren" in text or "trenbolone" in text:
        return "trenbolone"
    if "anavar" in text:
        return "anavar"
    if "primobolan" in text:
        return "primobolan"
    if "testosterone" in text:
        return "testosterone"
    if "peptide" in text:
        return "peptides"
    return "general"

def embed_batch(texts):
    r = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120
    )

    payload = r.json()
    if "data" not in payload:
        raise RuntimeError(f"Embedding failure: {payload}")

    return [d["embedding"] for d in payload["data"]]

# =======================
# MAIN
# =======================
def main():
    print("🔥 FULL GLOBAL REINDEX STARTED")

    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)

    total = 0

    for channel_dir in TRANSCRIPTS_DIR.iterdir():
        if not channel_dir.is_dir():
            continue

        channel = channel_dir.name

        for file in channel_dir.glob("*.txt"):
            raw = file.read_text(errors="ignore").lower()
            chunks = chunk_text(raw)

            if not chunks:
                continue

            embeddings = embed_batch(chunks)
            vectors = []

            for text, vec in zip(chunks, embeddings):
                vectors.append({
                    "id": stable_id(text),
                    "values": vec,
                    "metadata": {
                        "channel": channel,
                        "source": file.name,
                        "audience": infer_audience(text),
                        "topic": infer_topic(text),
                        "text": text[:1000]
                    }
                })

            index.upsert(vectors=vectors)
            total += len(vectors)

            print(f"✅ {channel}/{file.name}: {len(vectors)} chunks")

            time.sleep(0.3)

    print(f"\n🔥 COMPLETE — {total} TOTAL VECTORS INDEXED")

if __name__ == "__main__":
    main()
