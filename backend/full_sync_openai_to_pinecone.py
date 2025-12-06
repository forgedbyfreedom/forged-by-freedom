import os
import re
import glob
import unicodedata
from tqdm import tqdm
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# === Environment ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise ValueError("❌ Missing environment variables for OpenAI or Pinecone")

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
index = None

# === Ensure Pinecone index exists ===
if INDEX_NAME not in [i["name"] for i in pc.list_indexes()]:
    print(f"⚙️ Creating Pinecone index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(INDEX_NAME)

# === Utility: Chunk text safely ===
def chunk_text(text, max_chars=6000):
    paragraphs = text.split("\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 1 > max_chars:
            chunks.append(current.strip())
            current = para
        else:
            current += "\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks

# === Utility: Skip files with non-ASCII names ===
def is_ascii_safe(filename: str) -> bool:
    try:
        filename.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False

# === Start sync ===
transcripts = sorted(glob.glob("transcripts/*.txt"))
print(f"📚 Found {len(transcripts)} transcript files to sync")

for path in tqdm(transcripts, desc="Uploading transcripts"):
    filename = os.path.basename(path)

    # Skip bad filenames
    if not is_ascii_safe(filename):
        print(f"⚠️ Skipping file with non-ASCII name: {filename}")
        continue

    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        print(f"⚠️ Skipping empty file: {filename}")
        continue

    chunks = chunk_text(text)
    vectors = []

    for i, chunk in enumerate(chunks):
        try:
            emb = client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk
            )
            vector = emb.data[0].embedding
            vectors.append({
                "id": f"{re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)}-{i}",
                "values": vector,
                "metadata": {"source": filename, "chunk": i}
            })
        except Exception as e:
            print(f"⚠️ Error embedding chunk {i} in {filename}: {e}")

    if vectors:
        try:
            index.upsert(vectors=vectors)
            print(f"✅ Uploaded {len(vectors)} chunks from {filename}")
        except Exception as e:
            print(f"❌ Failed to upsert {filename}: {e}")

print("🎉 Sync complete — all valid transcripts uploaded to Pinecone!")
