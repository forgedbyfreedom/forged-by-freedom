#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Forged By Freedom – Pinecone Ingest
SAFE, LOCKED, TOKEN-BOUNDED, RESUMABLE
"""

import os
import sys
import time
import json
import hashlib
import signal
import atexit
from pathlib import Path
from typing import List

import tiktoken
from openai import OpenAI
from pinecone import Pinecone

# ==============================
# CONFIG
# ==============================

BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"

LOCK_FILE = BASE_DIR / ".ingest.lock"

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
EMBED_MODEL = "text-embedding-3-large"

MAX_TOKENS = 280_000          # safely under OpenAI hard limit
CHUNK_OVERLAP = 200
UPSERT_BATCH_SIZE = 50

# ==============================
# ENV VALIDATION
# ==============================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY not set")

if not PINECONE_API_KEY:
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# ==============================
# INGEST LOCK (REAL, SAFE)
# ==============================

def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

if LOCK_FILE.exists():
    try:
        old_pid = int(LOCK_FILE.read_text().strip())
        if pid_alive(old_pid):
            print("❌ Ingest already running — exiting.")
            sys.exit(1)
        else:
            LOCK_FILE.unlink()
    except Exception:
        LOCK_FILE.unlink()

LOCK_FILE.write_text(str(os.getpid()))

def cleanup(*_):
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
    sys.exit(0)

atexit.register(cleanup)
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# ==============================
# CLIENTS
# ==============================

openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

# ==============================
# TOKENIZER
# ==============================

tokenizer = tiktoken.get_encoding("cl100k_base")

def token_count(text: str) -> int:
    return len(tokenizer.encode(text))

# ==============================
# TEXT CHUNKING (SAFE)
# ==============================

def chunk_text(text: str) -> List[str]:
    tokens = tokenizer.encode(text)

    chunks = []
    start = 0

    while start < len(tokens):
        end = min(start + MAX_TOKENS, len(tokens))
        chunk = tokenizer.decode(tokens[start:end])
        chunks.append(chunk)
        start = end - CHUNK_OVERLAP

        if start < 0:
            start = 0

    return chunks

# ==============================
# VECTOR ID (ASCII SAFE)
# ==============================

def make_vector_id(path: Path, chunk_idx: int) -> str:
    base = f"{path.as_posix()}::{chunk_idx}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

# ==============================
# EMBEDDING
# ==============================

def embed_texts(texts: List[str]) -> List[List[float]]:
    response = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in response.data]

# ==============================
# INGEST
# ==============================

def ingest():
    print("🔍 INGEST STARTUP DEBUG")
    print(f"• BASE_DIR: {BASE_DIR}")
    print(f"• CHANNELS_DIR exists: {CHANNELS_DIR.exists()}")
    print(f"• Pinecone index: {INDEX_NAME}")
    print(f"• Embedding model: {EMBED_MODEL}")

    files = list(CHANNELS_DIR.rglob("*.txt"))
    print(f"• Total .txt files: {len(files)}")
    print("🚀 BEGIN INGEST\n")

    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue

            chunks = chunk_text(text)

            for i in range(0, len(chunks), UPSERT_BATCH_SIZE):
                batch_chunks = chunks[i:i + UPSERT_BATCH_SIZE]
                embeddings = embed_texts(batch_chunks)

                vectors = []
                for idx, emb in enumerate(embeddings):
                    vectors.append({
                        "id": make_vector_id(file_path, i + idx),
                        "values": emb,
                        "metadata": {
                            "source": file_path.name,
                            "path": str(file_path),
                            "chunk": i + idx
                        }
                    })

                index.upsert(vectors=vectors)
                time.sleep(0.2)  # gentle throttle

            print(f"✅ Ingested: {file_path.name}")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"❌ Failed: {file_path.name} — {e}")

# ==============================
# ENTRY
# ==============================

if __name__ == "__main__":
    ingest()
