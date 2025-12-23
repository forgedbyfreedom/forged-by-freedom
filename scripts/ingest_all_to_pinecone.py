#!/usr/bin/env python3
import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from pinecone import Pinecone

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

TRANSCRIPTS = ROOT / "transcripts_all"

PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
INDEX_NAME = (os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

if not PINECONE_API_KEY:
    raise SystemExit("❌ Missing PINECONE_API_KEY")
if not OPENROUTER_API_KEY:
    raise SystemExit("❌ Missing OPENROUTER_API_KEY")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

def embed(text: str):
    r = requests.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBED_MODEL, "input": text},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]

batch = []
BATCH_SIZE = 50

for channel_dir in TRANSCRIPTS.iterdir():
    if not channel_dir.is_dir():
        continue

    for txt in channel_dir.glob("*.txt"):
        text = txt.read_text(errors="ignore").strip()
        if len(text) < 200:
            continue

        vec = embed(text[:8000])

        batch.append({
            "id": f"{channel_dir.name}:{txt.stem}",
            "values": vec,
            "metadata": {
                "channel": channel_dir.name,
                "episode": txt.stem,
                "text": text[:2000],
                "source": f"{channel_dir.name} / {txt.name}",
                "path": str(txt.relative_to(ROOT)),
            }
        })

        if len(batch) >= BATCH_SIZE:
            index.upsert(vectors=batch)
            batch.clear()

if batch:
    index.upsert(vectors=batch)

print("✅ Pinecone ingestion complete")
