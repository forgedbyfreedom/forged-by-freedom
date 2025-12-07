import os
import tiktoken
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# === Load Environment Variables ===
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

INDEX_NAME = "forged-freedom-ai"

# === Ensure Pinecone Index Exists ===
if INDEX_NAME not in pc.list_indexes().names():
    print(f"🪶 Creating Pinecone index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(INDEX_NAME)

# === Utility ===
def chunk_text(text, max_tokens=4000):
    """Split large transcripts into smaller chunks for embedding."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    for i in range(0, len(tokens), max_tokens):
        yield enc.decode(tokens[i:i + max_tokens])

# === Process Each Transcript File ===
root_dir = os.getcwd()
transcript_files = []
for root, _, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".txt"):
            transcript_files.append(os.path.join(root, file))

print(f"📚 Found {len(transcript_files)} transcript files to index...")

for file_path in transcript_files:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        if not text.strip():
            continue

        print(f"🧩 Chunking {file_path}...")
        chunks = list(chunk_text(text, max_tokens=3500))
        print(f"➡️  Created {len(chunks)} chunks from {file_path}")

        vectors = []
        for i, chunk in enumerate(chunks):
            embedding = client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk
            ).data[0].embedding
            vectors.append({
                "id": f"{os.path.basename(file_path)}_{i}",
                "values": embedding,
                "metadata": {
                    "source": file_path,
                    "chunk_index": i,
                    "text": chunk[:2000]  # preview text
                }
            })

        print(f"⬆️  Uploading {len(vectors)} vectors to Pinecone...")
        index.upsert(vectors)
        print(f"✅ Indexed {file_path} successfully!")

    except Exception as e:
        print(f"❌ Error indexing {file_path}: {e}")

print("🎯 All transcript indexing complete.")
