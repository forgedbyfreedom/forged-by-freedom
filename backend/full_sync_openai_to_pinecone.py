"""
🌐 Full OpenAI → Pinecone Sync (Auto-Safe Version)
--------------------------------------------------
Uploads all transcript .txt files to Pinecone with
chunking, embedding creation, and safe ASCII vector IDs.
"""

import os
import glob
import re
import time
import unicodedata
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# === Load environment ===
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise ValueError("❌ Missing required API keys in environment variables!")

# === Initialize clients ===
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Ensure index exists
if PINECONE_INDEX_NAME not in [i.name for i in pc.list_indexes()]:
    print(f"⚙️ Creating new Pinecone index: {PINECONE_INDEX_NAME}")
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    time.sleep(5)

index = pc.Index(PINECONE_INDEX_NAME)

# === Helpers ===

def sanitize_id(text: str) -> str:
    """Make Pinecone-safe ASCII ID."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", text)
    return text

def chunk_text(text, max_tokens=8000):
    """Split text into chunks safe for embedding model."""
    words = text.split()
    chunks, current = [], []
    count = 0
    for w in words:
        count += len(w.split())
        current.append(w)
        if count >= max_tokens:
            chunks.append(" ".join(current))
            current, count = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks

# === Main Sync ===

transcripts = sorted(glob.glob("**/*.txt", recursive=True))
print(f"📚 Found {len(transcripts)} transcript files to sync")

total_files = 0
total_chunks = 0

for path in tqdm(transcripts, desc="Uploading transcripts"):
    filename = os.path.basename(path)
    safe_id = sanitize_id(filename)

    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception as e:
        print(f"⚠️ Could not read {filename}: {e}")
        continue

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
                "id": f"{safe_id}-{i}",
                "values": embedding,
                "metadata": {
                    "source": safe_id,
                    "chunk": i,
                    "original_filename": filename
                }
            })
        except Exception as e:
            print(f"⚠️ Skipping chunk {i} from {filename}: {e}")

    if vectors:
        try:
            index.upsert(vectors=vectors)
            total_files += 1
            total_chunks += len(vectors)
            print(f"✅ Uploaded {len(vectors)} chunks from {safe_id}")
        except Exception as e:
            print(f"❌ Pinecone upload failed for {safe_id}: {e}")

print("🎉 Sync Complete!")
print(f"✅ Files uploaded: {total_files}")
print(f"🧩 Total chunks embedded: {total_chunks}")
print(f"📦 Pinecone index: {PINECONE_INDEX_NAME}")
