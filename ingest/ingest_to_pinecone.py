import os
import sys
import time
import hashlib
from pathlib import Path

import tiktoken
from openai import OpenAI
from pinecone import Pinecone

# ======================
# CONFIG
# ======================
INDEX_NAME = "forged-freedom-ai"
NAMESPACE = "default"
EMBED_MODEL = "text-embedding-3-large"

MAX_TOKENS_PER_CHUNK = 200_000   # SAFELY below OpenAI 300k hard limit
BATCH_SIZE = 50                  # embedding batch size
LOCK_FILE = "/tmp/forged_ingest.lock"

BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"

# ======================
# SAFETY: SINGLE RUN LOCK
# ======================
if os.path.exists(LOCK_FILE):
    print("❌ Ingest already running — exiting.")
    sys.exit(1)

with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))

# ======================
# ENV CHECKS
# ======================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY not set")
if not PINECONE_API_KEY:
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# ======================
# CLIENTS
# ======================
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

# ======================
# TOKENIZER
# ======================
enc = tiktoken.get_encoding("cl100k_base")

def token_len(text: str) -> int:
    return len(enc.encode(text))

def chunk_text(text: str):
    tokens = enc.encode(text)
    for i in range(0, len(tokens), MAX_TOKENS_PER_CHUNK):
        yield enc.decode(tokens[i:i + MAX_TOKENS_PER_CHUNK])

# ======================
# EMBEDDING
# ======================
def embed_texts(texts):
    try:
        res = openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=texts
        )
        return [d.embedding for d in res.data]
    except Exception as e:
        print(f"❌ Embed failed batch: {e}")
        return []

# ======================
# INGEST
# ======================
def ingest():
    files = list(CHANNELS_DIR.rglob("*.txt"))
    print(f"• Total .txt files: {len(files)}")
    print("🚀 BEGIN INGEST\n")

    for file in files:
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
            total_tokens = token_len(text)

            if total_tokens == 0:
                continue

            chunks = list(chunk_text(text))

            vectors = []
            texts = []

            for idx, chunk in enumerate(chunks):
                texts.append(chunk)

                uid = hashlib.sha256(
                    f"{file.name}|{idx}".encode()
                ).hexdigest()

                vectors.append((uid, None, {
                    "file": file.name,
                    "chunk": idx
                }))

                if len(texts) >= BATCH_SIZE:
                    embeddings = embed_texts(texts)
                    if embeddings:
                        upserts = []
                        for (vid, _, meta), emb in zip(vectors, embeddings):
                            upserts.append((vid, emb, meta))
                        index.upsert(upserts, namespace=NAMESPACE)

                    texts.clear()
                    vectors.clear()

            # flush remainder
            if texts:
                embeddings = embed_texts(texts)
                if embeddings:
                    upserts = []
                    for (vid, _, meta), emb in zip(vectors, embeddings):
                        upserts.append((vid, emb, meta))
                    index.upsert(upserts, namespace=NAMESPACE)

            print(f"✅ Ingested: {file.name}")

        except Exception as e:
            print(f"⚠️ Skipped {file.name}: {e}")

    print("\n🎯 INGEST COMPLETE")

# ======================
# RUN
# ======================
try:
    ingest()
finally:
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
