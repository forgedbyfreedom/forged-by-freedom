#!/usr/bin/env python3
import os
import uuid
from pathlib import Path
from tqdm import tqdm
import requests
from pinecone import Pinecone
from dotenv import load_dotenv


# --------------------------------------------------
# ENV (CORRECT)
# --------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

assert PINECONE_API_KEY, "Missing PINECONE_API_KEY"
assert OPENROUTER_API_KEY, "Missing OPENROUTER_API_KEY"


# --------------------------------------------------
# PATHS
# --------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "transcripts_all"


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def chunk_text(text, size=1200, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


# --------------------------------------------------
# CLIENTS
# --------------------------------------------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)


files = list(TRANSCRIPTS.rglob("*.txt"))
print(f"📄 Found {len(files)} transcript files")


# --------------------------------------------------
# INGEST
# --------------------------------------------------
for file in tqdm(files, desc="Uploading"):
    try:
        text = file.read_text(errors="ignore")
        if len(text) < 500:
            continue

        channel = file.parent.name
        title = file.stem

        for i, chunk in enumerate(chunk_text(text)):
            resp = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={"model": "text-embedding-3-large", "input": chunk},
                timeout=30
            )
            resp.raise_for_status()

            embedding = resp.json()["data"][0]["embedding"]

            index.upsert([{
                "id": str(uuid.uuid4()),
                "values": embedding,
                "metadata": {
                    "channel": channel,
                    "title": title,
                    "chunk": i,
                    "text": chunk
                }
            }])

    except Exception as e:
        print(f"⚠️ Failed {file}: {e}")

print("✅ MASTER INGEST COMPLETE")
