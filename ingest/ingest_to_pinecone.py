import os
import sys
import time
import json
import hashlib
from pathlib import Path
from collections import defaultdict

import tiktoken
from openai import OpenAI
from pinecone import Pinecone

# ---------------- CONFIG ----------------
BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
EMBED_MODEL = "text-embedding-3-large"

CHUNK_TOKENS = 3000
EMBED_BATCH = 16
SLEEP_BETWEEN_BATCHES = 0.3

# ----------------------------------------

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("❌ OPENAI_API_KEY not set")

if not os.getenv("PINECONE_API_KEY"):
    raise RuntimeError("❌ PINECONE_API_KEY not set")

client = OpenAI()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(INDEX_NAME)

tokenizer = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))

def chunk_text(text: str):
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), CHUNK_TOKENS):
        yield tokenizer.decode(tokens[i:i + CHUNK_TOKENS])

def file_hash(path: Path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def embed_batch(texts):
    res = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]

def ingest():
    print("\n🔍 INGEST STARTUP DEBUG")
    print(f"• CHANNELS_DIR exists: {CHANNELS_DIR.exists()}")
    print(f"• Pinecone index: {INDEX_NAME}")
    print(f"• Embedding model: {EMBED_MODEL}")
    print(f"• Chunk tokens: {CHUNK_TOKENS} | Embed batch: {EMBED_BATCH}")

    txt_files = list(CHANNELS_DIR.rglob("*.txt"))
    total_files = len(txt_files)

    print(f"• Total episodes (.txt): {total_files}")
    print("🚀 BEGIN INGEST\n")

    episode_count = 0
    word_count = 0

    for txt in txt_files:
        try:
            text = txt.read_text(errors="ignore")
            words = len(text.split())
            chunks = list(chunk_text(text))

            vectors = []
            for i in range(0, len(chunks), EMBED_BATCH):
                batch = chunks[i:i + EMBED_BATCH]
                embeds = embed_batch(batch)

                for chunk_text_, emb in zip(batch, embeds):
                    vec_id = hashlib.sha1(chunk_text_.encode()).hexdigest()
                    vectors.append({
                        "id": vec_id,
                        "values": emb,
                        "metadata": {
                            "file": txt.name,
                            "path": str(txt),
                            "words": words
                        }
                    })

                index.upsert(vectors=vectors)
                vectors.clear()
                time.sleep(SLEEP_BETWEEN_BATCHES)

            episode_count += 1
            word_count += words

            print(f"✅ Ingested: {txt.name} | words: {words}")

            print(
                f"📊 Progress: {episode_count}/{total_files} episodes | "
                f"{word_count:,} total words"
            )

        except Exception as e:
            print(f"❌ Failed: {txt.name} — {e}")

    print("\n✅ INGEST COMPLETE")
    print(f"📚 Episodes ingested: {episode_count}")
    print(f"📝 Total words: {word_count:,}")

if __name__ == "__main__":
    ingest()
