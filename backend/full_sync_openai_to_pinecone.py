"""
🌐 Full OpenAI → Pinecone Sync (chunk-safe version)
--------------------------------------------------
Automatically syncs all transcript files in /transcripts
to your Pinecone vector index, splitting large files
to stay within OpenAI model limits.
"""

import os
import glob
from tqdm import tqdm
from openai import OpenAI
import pinecone

# === Environment variables ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise RuntimeError("❌ Missing required environment variables (OpenAI or Pinecone key).")

# === Clients ===
client = OpenAI(api_key=OPENAI_API_KEY)
pinecone.init(api_key=PINECONE_API_KEY)

INDEX_NAME = "forged-freedom-ai"

# Create index if missing
if INDEX_NAME not in [i.name for i in pinecone.list_indexes()]:
    print(f"🪶 Creating Pinecone index: {INDEX_NAME}")
    pinecone.create_index(INDEX_NAME, dimension=3072)

index = pinecone.Index(INDEX_NAME)

# === Helper: Safe chunking ===
def chunk_text(text: str, max_chars: int = 10000):
    """Split text safely within OpenAI token limits."""
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

# === Sync transcripts ===
transcripts = sorted(glob.glob("transcripts/*.txt"))
print(f"📚 Found {len(transcripts)} transcript files to sync")

for path in tqdm(transcripts, desc="Uploading transcripts"):
    filename = os.path.basename(path)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    chunks = chunk_text(text)
    vectors = []

    for i, chunk in enumerate(chunks):
        try:
            resp = client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk
            )
            embedding = resp.data[0].embedding
            vectors.append({
                "id": f"{filename}-{i}",
                "values": embedding,
                "metadata": {"source": filename, "chunk": i}
            })
        except Exception as e:
            print(f"⚠️ Skipping chunk {i} from {filename}: {e}")

    if vectors:
        index.upsert(vectors=vectors)
        print(f"✅ Uploaded {len(vectors)} chunks from {filename}")

print("🎉 All transcripts uploaded successfully to Pinecone!")
