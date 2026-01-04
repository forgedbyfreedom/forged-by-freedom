import os
import time
import hashlib
from pathlib import Path
from typing import List

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# ==============================
# CONFIG
# ==============================

EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 3072

CHUNK_SIZE = 800          # tokens-ish (safe)
CHUNK_OVERLAP = 100
BATCH_SIZE = 40           # keeps Pinecone < 2MB
EMBED_DELAY = 0.8         # seconds between OpenAI calls

CHANNELS_DIR = Path("ingest/channels")
NAMESPACE = "thinkbig"

# ==============================
# ENV CHECK
# ==============================

REQUIRED_ENVS = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX_NAME",
]

for env in REQUIRED_ENVS:
    if not os.getenv(env):
        raise RuntimeError(f"❌ Missing env var: {env}")

print("✅ Environment variables verified")

# ==============================
# CLIENTS
# ==============================

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

# ==============================
# HELPERS
# ==============================

def chunk_text(text: str) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i + CHUNK_SIZE]
        chunks.append(" ".join(chunk))
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def embed_batch(texts: List[str]) -> List[List[float]]:
    response = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=texts,
    )
    return [d.embedding for d in response.data]


def file_id(path: Path) -> str:
    return hashlib.md5(str(path).encode()).hexdigest()


# ==============================
# MAIN INGEST
# ==============================

def run():
    print("🚀 STARTING OPENAI → PINECONE INGEST")
    print(f"📂 Scanning transcripts in: {CHANNELS_DIR.resolve()}")

    files = sorted(CHANNELS_DIR.rglob("*.txt"))
    print(f"📄 Found {len(files)} transcript files")

    total_vectors = 0

    for file_path in files:
        try:
            text = file_path.read_text(errors="ignore").strip()
            if not text:
                continue

            chunks = chunk_text(text)
            print(f"➡️ {file_path.name}: {len(chunks)} chunks")

            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i:i + BATCH_SIZE]

                embeddings = embed_batch(batch)

                vectors = []
                for j, emb in enumerate(embeddings):
                    vectors.append({
                        "id": f"{file_id(file_path)}_{i+j}",
                        "values": emb,
                        "metadata": {
                            "source": str(file_path),
                            "chunk": i + j
                        }
                    })

                index.upsert(vectors=vectors, namespace=NAMESPACE)
                total_vectors += len(vectors)

                print(f"   ✅ Upserted {len(vectors)} vectors (total: {total_vectors})")

                time.sleep(EMBED_DELAY)

        except KeyboardInterrupt:
            print("🛑 Interrupted by user — safe to resume later")
            return
        except Exception as e:
            print(f"⚠️ Error processing {file_path.name}: {e}")
            continue

    print("🎉 INGEST COMPLETE")
    print(f"📊 Total vectors ingested: {total_vectors}")


if __name__ == "__main__":
    run()
