import os
import hashlib
import tiktoken
from pathlib import Path
from typing import List
from pinecone import Pinecone
from openai import OpenAI

# ================= CONFIG =================

BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"
MANIFEST_PATH = BASE_DIR / "manifest.json"

INDEX_NAME = "forged-freedom-ai"
NAMESPACE = "default"

EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 3072

MAX_TOKENS_PER_CHUNK = 8000
BATCH_SIZE = 50

# ================= SAFETY CHECKS =================

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("❌ OPENAI_API_KEY not set")

if not os.getenv("PINECONE_API_KEY"):
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# ================= CLIENTS =================

client = OpenAI()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(INDEX_NAME)

encoder = tiktoken.get_encoding("cl100k_base")

# ================= HELPERS =================

def tokenize(text: str) -> List[int]:
    return encoder.encode(text)

def detokenize(tokens: List[int]) -> str:
    return encoder.decode(tokens)

def chunk_text(text: str) -> List[str]:
    tokens = tokenize(text)
    chunks = []
    for i in range(0, len(tokens), MAX_TOKENS_PER_CHUNK):
        chunk = detokenize(tokens[i:i + MAX_TOKENS_PER_CHUNK])
        chunks.append(chunk)
    return chunks

def make_id(path: str, chunk_index: int) -> str:
    raw = f"{path}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ================= INGEST =================

def ingest():
    print("🔍 INGEST STARTUP DEBUG")
    print(f"• BASE_DIR: {BASE_DIR}")
    print(f"• CHANNELS_DIR exists: {CHANNELS_DIR.exists()}")
    print(f"• Total .txt files: {len(list(CHANNELS_DIR.rglob('*.txt')))}")
    print(f"• Pinecone index: {INDEX_NAME}")
    print(f"• Embedding model: {EMBED_MODEL}")
    print("🚀 BEGIN INGEST\n")

    for category in sorted(CHANNELS_DIR.iterdir()):
        if not category.is_dir():
            continue

        print(f"📂 CATEGORY: {category.name}")

        for file in category.rglob("*.txt"):
            try:
                text = file.read_text(encoding="utf-8", errors="ignore").strip()
                if not text:
                    continue

                chunks = chunk_text(text)

                vectors = []
                for i, chunk in enumerate(chunks):
                    emb = client.embeddings.create(
                        model=EMBED_MODEL,
                        input=chunk
                    ).data[0].embedding

                    vectors.append({
                        "id": make_id(str(file), i),
                        "values": emb,
                        "metadata": {
                            "source": file.name,
                            "category": category.name,
                            "chunk": i,
                            "path": str(file)
                        }
                    })

                for i in range(0, len(vectors), BATCH_SIZE):
                    index.upsert(
                        vectors=vectors[i:i + BATCH_SIZE],
                        namespace=NAMESPACE
                    )

            except Exception as e:
                print(f"❌ Failed: {file.name} — {e}")

    print("\n✅ INGEST COMPLETE")

# ================= ENTRY =================

if __name__ == "__main__":
    ingest()
