#!/usr/bin/env python3
import os
import uuid
import re
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone
import requests
from tqdm import tqdm

# ---------------- ENV ----------------
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
EMBED_MODEL = "text-embedding-3-large"

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS_ROOT = ROOT / "transcripts_all"
TRANSCRIPTS_ROOT.mkdir(exist_ok=True)

# ---------------- DISCOVER ----------------
SEARCH_DIRS = [
    ROOT / "transcripts",
    ROOT / "split_transcripts",
]

def discover_txt_files():
    files = []
    for base in SEARCH_DIRS:
        if not base.exists():
            continue
        for f in base.rglob("*.txt"):
            files.append(f)
    return files

# ---------------- NORMALIZE ----------------
def normalize_filename(path: Path):
    channel = path.parent.name.replace("@", "")
    title = path.stem
    return channel, title

def chunk_text(text, size=1200, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start+size])
        start += size - overlap
    return chunks

# ---------------- INIT PINECONE ----------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

# ---------------- INGEST ----------------
files = discover_txt_files()
print(f"📄 Found {len(files)} transcript files")

for file in tqdm(files):
    try:
        text = file.read_text(errors="ignore")
        if len(text) < 500:
            continue

        channel, title = normalize_filename(file)
        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            emb = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={"model": EMBED_MODEL, "input": chunk},
                timeout=30
            ).json()["data"][0]["embedding"]

            index.upsert([{
                "id": str(uuid.uuid4()),
                "values": emb,
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
