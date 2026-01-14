#!/usr/bin/env python3
"""
🔥 Reindex Female-Specific Steroid Content
------------------------------------------
• Re-embeds EXISTING transcripts
• Targets female / virilization content
• Writes to Pinecone namespace: women_steroids
• Safe against OpenRouter failures
"""

import os
import time
import json
import requests
from pathlib import Path
from pinecone import Pinecone

# =======================
# ENV
# =======================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")

assert OPENROUTER_API_KEY, "OPENROUTER_API_KEY missing"
assert PINECONE_API_KEY, "PINECONE_API_KEY missing"
assert PINECONE_HOST, "PINECONE_HOST missing"

INDEX_NAME = "forged-freedom-ai"
NAMESPACE = "women_steroids"
EMBED_MODEL = "text-embedding-3-large"

TRANSCRIPTS_DIR = Path("transcripts")

# =======================
# KEYWORDS
# =======================
FEMALE_KEYWORDS = [
    "women", "female", "viril", "voice", "clit",
    "mascul", "androgen", "irreversible",
    "fertility", "menstrual", "hair growth",
    "tren", "trenbolone", "anavar", "primobolan"
]

# =======================
# HELPERS
# =======================
def chunk_text(text, max_chars=900):
    chunks, buf = [], ""
    for line in text.splitlines():
        if len(buf) + len(line) > max_chars:
            chunks.append(buf.strip())
            buf = ""
        buf += line + " "
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def embed_batch(texts, retries=3):
    for attempt in range(retries):
        r = requests.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": EMBED_MODEL,
                "input": texts
            },
            timeout=60
        )

        try:
            payload = r.json()
        except Exception:
            print("❌ Invalid JSON from OpenRouter")
            time.sleep(2)
            continue

        if "data" in payload:
            return [d["embedding"] for d in payload["data"]]

        print("⚠️ OpenRouter error:", payload)
        time.sleep(2)

    return []


# =======================
# MAIN
# =======================
def main():
    print("🔥 Reindexing women-focused steroid content…")

    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)

    upserted = 0

    for channel_dir in TRANSCRIPTS_DIR.iterdir():
        if not channel_dir.is_dir():
            continue

        for file in channel_dir.glob("*.txt"):
            text = file.read_text(errors="ignore").lower()

            if not any(k in text for k in FEMALE_KEYWORDS):
                continue

            chunks = chunk_text(text)
            embeddings = embed_batch(chunks)

            if not embeddings:
                print(f"⛔ Skipped {file.name} (embedding failure)")
                continue

            vectors = []
            for i, emb in enumerate(embeddings):
                vectors.append({
                    "id": f"{file.stem}_{i}",
                    "values": emb,
                    "metadata": {
                        "source": file.name,
                        "channel": channel_dir.name,
                        "audience": "female",
                        "topic": "steroids",
                        "text": chunks[i][:1000]
                    }
                })

            index.upsert(vectors=vectors, namespace=NAMESPACE)
            upserted += len(vectors)

            print(f"✅ {file.name}: +{len(vectors)} female vectors")

    print(f"\n🔥 DONE — upserted {upserted} vectors to '{NAMESPACE
