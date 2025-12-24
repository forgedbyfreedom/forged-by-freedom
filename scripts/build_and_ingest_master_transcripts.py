#!/usr/bin/env python3
import os
import re
import time
from pathlib import Path
from typing import List

from tqdm import tqdm
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI


# ---------------- ENV ----------------
ROOT = Path(__file__).resolve().parents[1]   # repo root when script is in /scripts
ENV_PATH = ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)

PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
PINECONE_INDEX = (os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
OPENROUTER_EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

assert PINECONE_API_KEY, "Missing PINECONE_API_KEY"
assert OPENROUTER_API_KEY, "Missing OPENROUTER_API_KEY"

# ---------------- PATHS ----------------
TRANSCRIPTS = ROOT / "transcripts_all"

# ---------------- HELPERS ----------------
def chunk_text(text: str, size: int = 1200, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += max(1, size - overlap)
    return chunks

def safe_id(s: str) -> str:
    # Pinecone IDs should be clean ASCII-ish; keep it simple
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_\-\.]", "", s)
    return s[:200] if len(s) > 200 else s

# ---------------- INIT ----------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)
or_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

files = list(TRANSCRIPTS.rglob("*.txt"))
print(f"📄 Found {len(files)} transcripts under {TRANSCRIPTS}")

# ---------------- INGEST ----------------
BATCH = 50

for file in tqdm(files):
    try:
        text = file.read_text(errors="ignore")
        if len(text) < 500:
            continue

        channel = file.parent.name
        title = file.stem

        vectors = []
        for i, chunk in enumerate(chunk_text(text)):
            emb = or_client.embeddings.create(
                model=OPENROUTER_EMBED_MODEL,
                input=chunk
            ).data[0].embedding

            vec_id = safe_id(f"{channel}-{title}-{i}")
            vectors.append({
                "id": vec_id,
                "values": emb,
                "metadata": {
                    "channel": channel,
                    "title": title,
                    "chunk": i,
                    "text": chunk,
                    "source": str(file.relative_to(ROOT))
                }
            })

            if len(vectors) >= BATCH:
                index.upsert(vectors=vectors)
                vectors = []
                time.sleep(0.1)

        if vectors:
            index.upsert(vectors=vectors)

    except Exception as e:
        print(f"⚠️ Failed {file}: {e}")

print("✅ MASTER INGEST COMPLETE")
