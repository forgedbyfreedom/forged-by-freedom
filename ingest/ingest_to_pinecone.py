import os
import sys
import hashlib
import time
from pathlib import Path

import tiktoken
from openai import OpenAI
from pinecone import Pinecone

# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"
MANIFEST_PATH = BASE_DIR / "manifest.txt"

INDEX_NAME = "forged-freedom-ai"
NAMESPACE = "transcripts"

EMBED_MODEL = "text-embedding-3-large"
MAX_TOKENS = 300000
CHUNK_TOKENS = 4000
UPSERT_BATCH = 100

LOCK_FILE = "/tmp/forged_ingest.lock"

# =========================
# SAFETY LOCK
# =========================
if os.path.exists(LOCK_FILE):
    print("❌ Ingest already running — exiting.")
    sys.exit(1)

with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))

# =========================
# ENV CHECK
# =========================
if not os.getenv("OPENAI_API_KEY"):
    os.remove(LOCK_FILE)
    raise RuntimeError("❌ OPENAI_API_KEY not set")

if not os.getenv("PINECONE_API_KEY"):
    os.remove(LOCK_FILE)
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# =========================
# CLIENTS
# =========================
openai_client = OpenAI()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(INDEX_NAME)

encoder = tiktoken.encoding_for_model("gpt-4o-mini")

# =========================
# HELPERS
# =========================
def ascii_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_manifest():
    if not MANIFEST_PATH.exists():
        return set()
    return set(MANIFEST_PATH.read_text().splitlines())

def save_manifest(ids):
    with open(MANIFEST_PATH, "a") as f:
        for i in ids:
            f.write(i + "\n")

def chunk_text(text):
    tokens = encoder.encode(text)
    if len(tokens) > MAX_TOKENS:
        return []
    for i in range(0, len(tokens), CHUNK_TOKENS):
        yield encoder.decode(tokens[i:i + CHUNK_TOKENS])

def embed(texts):
    res = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]

# =========================
# INGEST
# =========================
def ingest():
    print("🔍 INGEST STARTUP DEBUG")
    print(f"• BASE_DIR: {BASE_DIR}")
    print(f"• CHANNELS_DIR exists: {CHANNELS_DIR.exists()}")
    print(f"• Manifest exists: {MANIFEST_PATH.exists()}")
    print(f"• Pinecone index: {INDEX_NAME}")
    print(f"• Embedding model: {EMBED_MODEL}")

    manifest = load_manifest()

    files = list(CHANNELS_DIR.rglob("*.txt"))
    print(f"• Total .txt files: {len(files)}")
    print("🚀 BEGIN INGEST\n")

    for file in files:
        text = file.read_text(errors="ignore").strip()
        if not text:
            continue

        chunks = list(chunk_text(text))
        if not chunks:
            print(f"⚠️ Skipped oversized file: {file.name}")
            continue

        vectors = []
        ids_written = []

        for idx, chunk in enumerate(chunks):
            uid = ascii_id(f"{file}:{idx}")
            if uid in manifest:
                continue

            vectors.append({
                "id": uid,
                "values": None,  # placeholder
                "metadata": {
                    "source": str(file),
                    "chunk": idx
                }
            })
            ids_written.append(uid)

        if not vectors:
            continue

        texts = chunks[:len(vectors)]
        embeddings = embed(texts)

        for i, emb in enumerate(embeddings):
            vectors[i]["values"] = emb

        for i in range(0, len(vectors), UPSERT_BATCH):
            batch = vectors[i:i + UPSERT_BATCH]
            index.upsert(vectors=batch, namespace=NAMESPACE)
            time.sleep(0.2)

        save_manifest(ids_written)
        manifest.update(ids_written)

        print(f"✅ Ingested: {file.name}")

# =========================
# RUN
# =========================
try:
    ingest()
finally:
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
