import os
import time
import json
from tqdm import tqdm
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# ========== CONFIG ==========
TRANSCRIPTS_DIR = os.path.expanduser("~/forged-by-freedom/transcripts")
INDEX_NAME = "forged-transcripts"

# Read from environment variables (these must be set!)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Check environment
if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise EnvironmentError("❌ Missing OPENAI_API_KEY or PINECONE_API_KEY in environment variables!")

# Initialize clients
print("🔗 Connecting to OpenAI + Pinecone...")
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Ensure Pinecone index exists
if INDEX_NAME not in [idx["name"] for idx in pc.list_indexes()]:
    print(f"🪶 Creating Pinecone index: {INDEX_NAME} ...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=3072,  # for text-embedding-3-large
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    time.sleep(10)

index = pc.Index(INDEX_NAME)
print(f"✅ Using Pinecone index: {INDEX_NAME}")

# ========== LOAD TRANSCRIPTS ==========
def read_text_files(folder_path):
    files = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            path = os.path.join(folder_path, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        files.append({"id": filename, "text": content})
            except Exception as e:
                print(f"⚠️ Error reading {filename}: {e}")
    return files

print(f"📂 Scanning transcripts folder: {TRANSCRIPTS_DIR}")
transcripts = read_text_files(TRANSCRIPTS_DIR)
print(f"📄 Found {len(transcripts)} transcript files.")

if not transcripts:
    raise FileNotFoundError("No transcripts found in folder!")

# ========== EMBED AND UPLOAD ==========
def embed_and_upload(files):
    for file in tqdm(files, desc="🚀 Uploading to Pinecone"):
        text = file["text"]
        filename = file["id"]

        # Skip empty or duplicate entries
        if not text.strip():
            print(f"⚠️ Skipping empty file: {filename}")
            continue

        try:
            # Generate embedding
            embedding_response = client.embeddings.create(
                model="text-embedding-3-large",
                input=text[:8000]  # truncate to stay within token limit
            )
            vector = embedding_response.data[0].embedding

            # Upsert to Pinecone
            index.upsert([
                {
                    "id": filename,
                    "values": vector,
                    "metadata": {"filename": filename, "text": text[:500]}  # store preview
                }
            ])

        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")

# Run the upload
embed_and_upload(transcripts)

print("\n🎉 Done! All transcripts uploaded to Pinecone successfully.")
