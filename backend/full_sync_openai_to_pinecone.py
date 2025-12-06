import os
import glob
import re
import unicodedata
from tqdm import tqdm
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# === Initialize environment ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise ValueError("❌ Missing required API keys in environment variables.")

print("🚀 Running strict-safe Pinecone sync build")

# === Clients ===
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# === Ensure index exists ===
existing_indexes = [idx["name"] for idx in pc.list_indexes()]
if PINECONE_INDEX_NAME not in existing_indexes:
    print(f"🪄 Creating Pinecone index: {PINECONE_INDEX_NAME}")
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(PINECONE_INDEX_NAME)
print(f"✅ Using index: {PINECONE_INDEX_NAME}")

# === Helper functions ===
def chunk_text(text, max_tokens=8000):
    """Split long text into safe chunks for embedding."""
    words = text.split()
    chunks, current, count = [], [], 0
    for w in words:
        count += len(w.split())
        current.append(w)
        if count >= max_tokens:
            chunks.append(" ".join(current))
            current, count = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks

def sanitize_ascii(value: str) -> str:
    """Fully strip all non-ASCII and unsafe chars for Pinecone IDs."""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", value)
    value = value.strip("_")
    return value or "untitled"

# === Sync transcripts ===
transcripts = sorted(glob.glob("transcripts/*.txt"))
print(f"📚 Found {len(transcripts)} transcript files to sync")

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
            response = client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk
            )
            embedding = response.data[0].embedding
            vector_id = sanitize_ascii(f"{safe_id}-{i}")
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {"source": sanitize_ascii(filename), "chunk": i}
            })
        except Exception as e:
            print(f"⚠️ Skipping chunk {i} from {filename}: {e}")

    if not vectors:
        print(f"⚠️ No valid chunks in {filename}")
        continue

    print(f"🧩 Sample ID before upload: {vectors[0]['id']}")
    try:
        index.upsert(vectors=vectors)
        print(f"✅ Uploaded {len(vectors)} chunks from {safe_id}")
    except Exception as e:
        print(f"❌ Upload failed for {safe_id}: {e}")

# === Index summary ===
try:
    stats = index.describe_index_stats()
    print(f"📊 Pinecone index now has {stats['total_vector_count']} total vectors.")
except Exception as e:
    print(f"⚠️ Could not fetch Pinecone stats: {e}")

print("🎉 Sync complete.")
