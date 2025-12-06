#!/usr/bin/env python3
import os
import glob
import re
import unicodedata
from tqdm import tqdm
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

print("🧠 Active script version: 2025-12-06-strict-safe-final")

# === Load environment variables ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise ValueError("❌ Missing required API keys (OPENAI_API_KEY or PINECONE_API_KEY)")

# === Init clients ===
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# === Ensure Pinecone index exists ===
existing_indexes = [idx["name"] for idx in pc.list_indexes()]
if PINECONE_INDEX_NAME not in existing_indexes:
    print(f"🪄 Creating Pinecone index: {PINECONE_INDEX_NAME}")
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(PINECONE_INDEX_NAME)
print(f"✅ Using index: {PINECONE_INDEX_NAME}")

# === Helper functions ===
def sanitize_ascii(value: str) -> str:
    """Convert any string to fully ASCII-safe Pinecone ID."""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9_.-]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "untitled"

def chunk_text(text: str, max_tokens: int = 8000):
    """Split text into smaller chunks safe for OpenAI embeddings."""
    words = text.split()
    chunks, current, count = [], [], 0
    for word in words:
        count += 1
        current.append(word)
        if count >= max_tokens:
            chunks.append(" ".join(current))
            current, count = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks

# === Load transcript files ===
transcripts = sorted(glob.glob("transcripts/*.txt"))
print(f"📚 Found {len(transcripts)} transcript files to sync")

if not transcripts:
    print("⚠️ No transcripts found in /transcripts — nothing to sync.")
    exit(0)

# === Pre-sanitize all filenames on disk ===
for path in transcripts:
    directory = os.path.dirname(path)
    filename = os.path.basename(path)
    safe_filename = sanitize_ascii(filename)
    safe_path = os.path.join(directory, safe_filename)
    if safe_filename != filename:
        os.rename(path, safe_path)
        print(f"🔤 Renamed: {filename} → {safe_filename}")

# Re-list after renaming
transcripts = sorted(glob.glob("transcripts/*.txt"))
print("🧾 Filenames:", [os.path.basename(f) for f in transcripts])

# === Main sync loop ===
for path in tqdm(transcripts, desc="Uploading transcripts"):
    filename = os.path.basename(path)
    safe_id = sanitize_ascii(filename)

    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception as e:
        print(f"⚠️ Could not read {filename}: {e}")
        continue

    if not text:
        print(f"⚠️ Skipping empty file: {filename}")
        continue

    chunks = chunk_text(text)
    vectors = []

    for i, chunk in enumerate(chunks):
        try:
            resp = client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk,
            )
            embedding = resp.data[0].embedding
            raw_id = f"{safe_id}-{i}"
            vector_id = sanitize_ascii(raw_id)
            vector_id = vector_id.encode("ascii", "ignore").decode("ascii")

            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {"source": sanitize_ascii(filename), "chunk": int(i)},
            })
        except Exception as e:
            print(f"⚠️ Skipping chunk {i} from {filename}: {e}")

    if not vectors:
        print(f"⚠️ No valid chunks in {filename}")
        continue

    print("🧩 Final vector IDs (first 3):", [v["id"] for v in vectors[:3]])

    try:
        index.upsert(vectors=vectors)
        print(f"✅ Uploaded {len(vectors)} chunks from {safe_id}")
    except Exception as e:
        print(f"❌ Upload failed for {safe_id}: {e}")

# === Summary ===
try:
    stats = index.describe_index_stats()
    print(f"📊 Pinecone index now has {stats['total_vector_count']} total vectors.")
except Exception as e:
    print(f"⚠️ Could not fetch Pinecone stats: {e}")

print("🎉 Sync complete — all filenames and IDs are ASCII-safe.")
