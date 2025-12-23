#!/usr/bin/env python3

import os
import requests
from pathlib import Path
from pinecone import Pinecone
from dotenv import load_dotenv

# ---------------- ENV ----------------
load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[1] / ".env",
    override=True
)

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "transcripts_all"

HEADERS = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
    "Content-Type": "application/json"
}

def embed(text):
    r = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers=HEADERS,
        json={"model": "text-embedding-3-large", "input": text},
        timeout=30
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]

for ch in TRANSCRIPTS.iterdir():
    if not ch.is_dir():
        continue

    for txt in ch.glob("*.txt"):
        text = txt.read_text(errors="ignore").strip()
        if len(text) < 300:
            continue

        vec = embed(text[:6000])

        index.upsert([{
            "id": f"{ch.name}:{txt.stem}",
            "values": vec,
            "metadata": {
                "channel": ch.name,
                "episode": txt.stem,
                "text": text[:1200]
            }
        }])

print("✅ Pinecone ingestion complete")
