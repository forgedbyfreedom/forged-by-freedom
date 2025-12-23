#!/usr/bin/env python3

import os
import uuid
import requests
from pathlib import Path
from tqdm import tqdm
from pinecone import Pinecone
from dotenv import load_dotenv

# ---------------- ENV ----------------
load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[1] / ".env",
    override=True
)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not all([PINECONE_API_KEY, OPENROUTER_API_KEY]):
    raise RuntimeError("❌ Missing API keys")

# ---------------- PATHS ----------------
ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "transcripts_all"

# ---------------- CLIENTS ----------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

# ---------------- UTILS ----------------
def chunk_text(text, size=1200, overlap=200):
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out

def embed(text):
    r = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={"model": "text-embedding-3-large", "input": text},
        timeout=30
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]

# ---------------- INGEST ----------------
files = list(TRANSCRIPTS.rglob("*.txt"))
print(f"📄 Found {len(files)} transcripts")

for f in tqdm(files):
    text = f.read_text(errors="ignore")
    if len(text) < 500:
        continue

    channel = f.parent.name
    title = f.stem

    for i, chunk in enumerate(chunk_text(text)):
        vec = embed(chunk)

        index.upsert([{
            "id": str(uuid.uuid4()),
            "values": vec,
            "metadata": {
                "channel": channel,
                "title": title,
                "chunk": i,
                "text": chunk[:1500],
                "source": f"{channel}/{f.name}"
            }
        }])

print("✅ MASTER INGEST COMPLETE")
