import os
import uuid
from pathlib import Path

from openai import OpenAI
from pinecone import Pinecone

# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

EMBED_MODEL = os.getenv(
    "OPENROUTER_EMBED_MODEL",
    "text-embedding-3-small"
)

# =========================
# CLIENTS
# =========================
openai_client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url=os.environ.get(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1"
    ),
)

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(os.environ["PINECONE_INDEX_NAME"])

# =========================
# HELPERS
# =========================
def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def embed_texts(texts):
    res = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]


# =========================
# INGEST
# =========================
def run():
    print("🚀 ONE-TIME OPENROUTER INGEST START")
    print(f"📂 Channels dir: {CHANNELS_DIR}")

    txt_files = list(CHANNELS_DIR.rglob("*.txt"))
    print(f"📄 Found {len(txt_files)} transcript files")

    total_vectors = 0

    for file in txt_files:
        channel = file.parent.name
        category = file.parent.parent.name if file.parent.parent else "uncategorized"

        text = file.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text)

        embeddings = embed_texts(chunks)

        vectors = []
        for chunk, emb in zip(chunks, embeddings):
            vectors.append({
                "id": str(uuid.uuid4()),
                "values": emb,
                "metadata": {
                    "source": file.name,
                    "channel": channel,
                    "category": category,
                    "text": chunk[:5000],  # Pinecone-safe
                }
            })

        index.upsert(vectors=vectors)
        total_vectors += len(vectors)

        print(f"✅ {file.name} → {len(vectors)} vectors")

    print("🎉 INGEST COMPLETE")
    print(f"📊 Total vectors upserted: {total_vectors}")


if __name__ == "__main__":
    run()
