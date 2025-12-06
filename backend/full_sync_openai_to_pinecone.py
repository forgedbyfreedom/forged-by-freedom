import os
import re
import glob
import unicodedata
from tqdm import tqdm
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# === ENV VARIABLES ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

# === Clients ===
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

# === Sanitize helper ===
def sanitize_id(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9_.-]", "_", text)
    return text

def chunk_text(text: str, max_len=7000):
    words, chunks, chunk = text.split(), [], []
    for w in words:
        if len(" ".join(chunk + [w])) > max_len:
            chunks.append(" ".join(chunk))
            chunk = [w]
        else:
            chunk.append(w)
    if chunk: chunks.append(" ".join(chunk))
    return chunks

# === Step 1: Cleanup filenames ===
for path in glob.glob("**/*.txt", recursive=True):
    folder, filename = os.path.split(path)
    safe = sanitize_id(filename)
    if safe != filename:
        os.rename(path, os.path.join(folder, safe))
        print(f"🧹 Renamed: {filename} → {safe}")

# === Step 2: Upload transcripts ===
transcripts = sorted(glob.glob("transcripts/*.txt"))
print(f"📚 Found {len(transcripts)} transcript files to sync")

for path in tqdm(transcripts, desc="Uploading transcripts"):
    filename = os.path.basename(path)
    safe_id = sanitize_id(filename)

    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    chunks, vectors = chunk_text(text), []

    for i, chunk in enumerate(chunks):
        try:
            emb = client.embeddings.create(model="text-embedding-3-large", input=chunk)
            vectors.append({
                "id": f"{safe_id}-{i}",
                "values": emb.data[0].embedding,
                "metadata": {"source": safe_id, "chunk": i}
            })
        except Exception as e:
            print(f"⚠️ Skipping {filename} chunk {i}: {e}")

    if vectors:
        index.upsert(vectors=vectors)
        print(f"✅ Uploaded {len(vectors)} chunks from {filename}")

print("🎉 Full sync completed successfully!")
