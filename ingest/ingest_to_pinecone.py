import os
import sys
import time
import hashlib
from pathlib import Path

import tiktoken
from openai import OpenAI
from pinecone import Pinecone

# ===============================
# CONFIG
# ===============================

BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
EMBED_MODEL = "text-embedding-3-large"

CHUNK_TOKENS = 3000
EMBED_BATCH_SIZE = 16

MAX_FILE_TOKENS = 2_000_000  # skip insane files safely

# ===============================
# SAFETY CHECKS
# ===============================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY not set")
if not PINECONE_API_KEY:
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# ===============================
# CLIENTS
# ===============================

openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

tokenizer = tiktoken.get_encoding("cl100k_base")

# ===============================
# GLOBAL METRICS
# ===============================

TOTAL_EPISODES = 0
TOTAL_WORDS = 0

INGESTED_EPISODES = 0
INGESTED_WORDS = 0
INGESTED_VECTORS = 0

START_TIME = time.time()

# ===============================
# HELPERS
# ===============================

def count_words(text: str) -> int:
    return len(text.split())

def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))

def chunk_text(text: str, max_tokens: int):
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), max_tokens):
        yield tokenizer.decode(tokens[i:i + max_tokens])

def file_hash(path: Path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()

def print_progress():
    elapsed = time.time() - START_TIME
    remaining = TOTAL_EPISODES - INGESTED_EPISODES

    eta = int((elapsed / INGESTED_EPISODES) * remaining) if INGESTED_EPISODES else 0

    print(
        f"📈 Progress: "
        f"{INGESTED_EPISODES}/{TOTAL_EPISODES} episodes | "
        f"{INGESTED_WORDS/1_000_000:.2f}M words | "
        f"{INGESTED_VECTORS:,} vectors | "
        f"ETA {eta//60}m {eta%60}s"
    )

# ===============================
# PRE-SCAN
# ===============================

print("🔍 INGEST STARTUP DEBUG")
print(f"• BASE_DIR: {BASE_DIR}")
print(f"• CHANNELS_DIR exists: {CHANNELS_DIR.exists()}")
print(f"• Pinecone index: {INDEX_NAME}")
print(f"• Embedding model: {EMBED_MODEL}")

for root, _, files in os.walk(CHANNELS_DIR):
    for f in files:
        if f.endswith(".txt"):
            TOTAL_EPISODES += 1
            with open(Path(root) / f, "r", errors="ignore") as fh:
                TOTAL_WORDS += count_words(fh.read())

print(f"• Total episodes: {TOTAL_EPISODES}")
print(f"• Total words: {TOTAL_WORDS:,}")
print("🚀 BEGIN INGEST\n")

# ===============================
# INGEST
# ===============================

for root, _, files in os.walk(CHANNELS_DIR):
    namespace = Path(root).name

    txt_files = [f for f in files if f.endswith(".txt")]
    if not txt_files:
        continue

    print(f"📂 CATEGORY: {namespace} (namespace: {namespace})")

    for filename in txt_files:
        path = Path(root) / filename

        with open(path, "r", errors="ignore") as fh:
            text = fh.read()

        token_count = count_tokens(text)
        if token_count > MAX_FILE_TOKENS:
            print(f"⚠️ Skipped huge file (> {MAX_FILE_TOKENS} tokens): {filename}")
            continue

        chunks = list(chunk_text(text, CHUNK_TOKENS))
        words = count_words(text)

        # Embed in batches
        vectors = []
        for i in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[i:i + EMBED_BATCH_SIZE]
            res = openai_client.embeddings.create(
                model=EMBED_MODEL,
                input=batch
            )

            for j, emb in enumerate(res.data):
                vector_id = f"{file_hash(path)}_{i+j}"
                vectors.append({
                    "id": vector_id,
                    "values": emb.embedding,
                    "metadata": {
                        "file": filename,
                        "namespace": namespace
                    }
                })

        index.upsert(vectors=vectors, namespace=namespace)

        INGESTED_EPISODES += 1
        INGESTED_WORDS += words
        INGESTED_VECTORS += len(vectors)

        print(f"✅ Ingested: {filename} ({len(vectors)} vectors)")
        print_progress()

print("\n✅ INGEST COMPLETE")
