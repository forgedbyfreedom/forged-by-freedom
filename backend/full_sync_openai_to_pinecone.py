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

print("🚀 Running latest full_sync_openai_to_pinecone.py version")
print(f"🔑 OpenAI key loaded: {bool(OPENAI_API_KEY)}")
print(f"🔑 Pinecone key loaded: {bool(PINECONE_API_KEY)}")

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
    """Split long text into chunks that fit within OpenAI embedding limits."""
    words = text.split()
    chunks = []
    current_chunk = []
    token_count = 0
    for word in words:
        token_count += len(word.split())
        current_chunk.append(word)
        if token_count >= max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk, token_count = [], 0
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def sanitize_id(text: str) -> str:
    """Convert filename to safe ASCII ID for Pinecone."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", text)
    return text

# === Sync transcripts ===
transcripts = sorted(glob.glob("transcripts/*.txt"))
print(f"📚 Found {len(transcripts)} transcript files to sync")

for path in tqdm(transcripts, desc="Uploading transcripts"):
    filename = os.path.basename(path)
    safe_id = sanitize_id(filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

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
            vector_id = f"{safe_id}-{i}"
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {"source": safe_id, "chunk": i}
            })
        except Exception as e:
            print(f"⚠️ Skipping chunk {i} from {filename}: {e}")

    if vectors:
        print(f"🧩 Sample ID: {vectors[0]['id']}")
        try:
            index.upsert(vectors=vectors)
            print(f"✅ Uploaded {len(vectors)} chunks from {safe_id}")
        except Exception as e:
            print(f"❌ Failed to upsert {filename}: {e}")

print("🎉 All transcripts uploaded successfully to Pinecone!")

# === Optional: Summary of index stats ===
try:
    stats = index.describe_index_stats()
    print(f"📊 Pinecone index contains {stats['total_vector_count']} vectors total.")
except Exception as e:
    print(f"⚠️ Could not fetch Pinecone stats: {e}")
