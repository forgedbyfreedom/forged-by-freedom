import os
import time
import hashlib
from pathlib import Path

import pinecone
from openai import OpenAI

# =========================
# CONFIG
# =========================
EMBED_MODEL = "text-embedding-3-large"
INDEX_NAME = "forged-freedom-ai"
NAMESPACE = "fbf"
BATCH_SIZE = 64
MAX_CHARS = 6000  # safe chunk size

BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"

# =========================
# CLIENTS
# =========================
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

pinecone.init(
    api_key=os.getenv("PINECONE_API_KEY"),
    environment=os.getenv("PINECONE_ENV"),
)
index = pinecone.Index(INDEX_NAME)

# =========================
# HELPERS
# =========================
def stable_id(path: Path, chunk_index: int) -> str:
    h = hashlib.sha1(f"{path}:{chunk_index}".encode()).hexdigest()
    return h

def chunk_text(text: str):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + MAX_CHARS])
        start += MAX_CHARS
    return chunks

def embed_texts(texts):
    response = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in response.data]

def already_exists(vector_ids):
    stats = index.fetch(ids=vector_ids, namespace=NAMESPACE)
    return set(stats.vectors.keys())

# =========================
# INGEST
# =========================
def ingest():
    print("🚀 STARTING SAFE INGEST (OpenAI embeddings)")
    files = list(CHANNELS_DIR.rglob("*.txt"))

    for file in files:
        text = file.read_text(errors="ignore")
        chunks = chunk_text(text)

        ids = [stable_id(file, i) for i in range(len(chunks))]
        existing = already_exists(ids)

        pending = []
        pending_ids = []

        for i, chunk in enumerate(chunks):
            vid = ids[i]
            if vid in existing:
                continue
            pending.append(chunk)
            pending_ids.append(vid)

        if not pending:
            continue

        print(f"📄 {file.name}: embedding {len(pending)} new chunks")

        for i in range(0, len(pending), BATCH_SIZE):
            batch_texts = pending[i:i + BATCH_SIZE]
            batch_ids = pending_ids[i:i + BATCH_SIZE]

            embeddings = embed_texts(batch_texts)

            vectors = [
                {
                    "id": batch_ids[j],
                    "values": embeddings[j],
                    "metadata": {
                        "source": str(file),
                        "chunk": j
                    }
                }
                for j in range(len(batch_texts))
            ]

            index.upsert(vectors=vectors, namespace=NAMESPACE)
            time.sleep(0.2)  # gentle rate limit

    print("✅ INGEST COMPLETE")

if __name__ == "__main__":
    ingest()
