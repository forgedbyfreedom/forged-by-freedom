#!/usr/bin/env python3
import os
import uuid
from pathlib import Path

import requests
from tqdm import tqdm
from dotenv import load_dotenv
from pinecone import Pinecone

# ---------------- ENV ----------------
ROOT = Path(__file__).resolve().parents[2]  # scripts/scripts/ -> repo root
load_dotenv(dotenv_path=ROOT / ".env", override=True)

PINECONE_API_KEY = (os.getenv("PINECONE_API_KEY") or "").strip()
PINECONE_INDEX = (os.getenv("PINECONE_INDEX_NAME") or "forged-freedom-ai").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
EMBED_MODEL = (os.getenv("OPENROUTER_EMBED_MODEL") or "text-embedding-3-large").strip()

if not PINECONE_API_KEY:
    raise SystemExit("❌ Missing PINECONE_API_KEY")
if not OPENROUTER_API_KEY:
    raise SystemExit("❌ Missing OPENROUTER_API_KEY")

# ---------------- PATHS ----------------
TRANSCRIPTS_ROOT = ROOT / "transcripts_all"
TRANSCRIPTS_ROOT.mkdir(exist_ok=True)

SEARCH_DIRS = [
    ROOT / "transcripts",
    ROOT / "split_transcripts",
    ROOT / "transcripts_all",
]

def discover_txt_files():
    files = []
    for base in SEARCH_DIRS:
        if not base.exists():
            continue
        files.extend(list(base.rglob("*.txt")))
    # de-dupe
    return sorted(set(files))

def normalize_filename(path: Path):
    channel = path.parent.name.replace("@", "").strip() or "unknown"
    title = path.stem
    return channel, title

def chunk_text(text: str, size: int = 2400, overlap: int = 300):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start+size])
        start += (size - overlap)
    return chunks

# ---------------- CLIENTS ----------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

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

# ---------------- INGEST ----------------
files = discover_txt_files()
print(f"📄 Found {len(files)} transcript files")

for file in tqdm(files, desc="Embedding + upserting"):
    try:
        text = file.read_text(errors="ignore").strip()
        if len(text) < 500:
            continue

        channel, title = normalize_filename(file)
        chunks = chunk_text(text)

        vectors = []
        for i, chunk in enumerate(chunks):
            vec = embed(chunk[:8000])
            vectors.append({
                "id": f"{channel}:{title}:{i}:{uuid.uuid4().hex[:8]}",
                "values": vec,
                "metadata": {
                    "channel": channel,
                    "title": title,
                    "chunk": i,
                    "text": chunk[:2000],
                    "source": f"{channel} / {file.name}",
                    "path": str(file.relative_to(ROOT)) if file.exists() else str(file),
                },
            })

        # upsert per file in one call (fewer requests)
        index.upsert(vectors=vectors)

    except Exception as e:
        print(f"⚠️ Failed {file}: {e}")

print("✅ MASTER INGEST COMPLETE")
