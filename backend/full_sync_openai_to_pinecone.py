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

# === Clients ===
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Ensure index exists
if PINECONE_INDEX_NAME not in [idx["name"] for idx in pc.list_indexes()]:
    print(f"🪄 Creating Pinecone index: {PINECONE_INDEX_NAME}")
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(PINECONE_INDEX_NAME)
print(f"✅ Using index: {PINECONE_INDEX_NAME}")

# === Helpers ===
def chunk_text(text, max_tokens=8000):
    """Split long text safely for embedding model."""
    words = text.split()
    chunks = []
    current = []
    count = 0
    for word in words:
        count += len(word.split())
        current.append(word)
        if count > max_tokens:
            chunks.append(" ".join(current))
            current, count = [], 0
    if current:
        chunks.append(" ".join(current))
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
                "metadata": {"source": filename, "chunk": i}
            })
        except Exception as e:
            print(f"⚠️ Skipping chunk {i} from {filename}: {e}")

    if vectors:
        index.upsert(vectors=vectors)
        print(f"✅ Uploaded {len(vectors)} chunks from {filename}")

print("🎉 All transcripts uploaded successfully to Pinecone!")
