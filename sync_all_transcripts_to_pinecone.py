# sync_all_transcripts_to_pinecone.py
# Upload all transcripts (including remote ones) to Pinecone, skipping duplicates.

import os
import requests
import hashlib
from tqdm import tqdm
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from pathlib import Path

# -----------------------------
# 🌍 Load Environment Variables
# -----------------------------
load_dotenv(dotenv_path=Path.cwd() / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "forged-transcripts")
PINECONE_REGION = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")

if not OPENAI_API_KEY:
    raise ValueError("❌ Missing OPENAI_API_KEY in your .env file.")
if not PINECONE_API_KEY:
    raise ValueError("❌ Missing PINECONE_API_KEY in your .env file.")

# -----------------------------
# ⚙️ Initialize Clients
# -----------------------------
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Create or connect to index
existing_indexes = [i["name"] for i in pc.list_indexes()]
if PINECONE_INDEX not in existing_indexes:
    print(f"🪶 Creating Pinecone index: {PINECONE_INDEX} ...")
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=3072,  # text-embedding-3-large has 3072 dims
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region=PINECONE_REGION)
    )
index = pc.Index(PINECONE_INDEX)
print(f"✅ Using Pinecone index: {PINECONE_INDEX}")

# -----------------------------
# 📂 Gather All Transcript Sources
# -----------------------------
LOCAL_FOLDER = Path(__file__).resolve().parent / "transcripts"
REMOTE_FILE_URLS = [
    # Add any remote transcript files here (OpenAI or cloud links)
]

def load_local_files():
    """Load .txt transcript files from the local transcripts/ folder."""
    files = []
    if LOCAL_FOLDER.exists():
        for f in LOCAL_FOLDER.iterdir():
            if f.suffix == ".txt":
                with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                    text = fp.read().strip()
                if text:
                    files.append({"id": f.name, "text": text})
    return files

def download_remote_files():
    """Download transcript text files from URLs (optional)."""
    files = []
    for url in REMOTE_FILE_URLS:
        print(f"🌐 Downloading remote file: {url}")
        try:
            response = requests.get(url, headers={"Authorization": f"Bearer {OPENAI_API_KEY}"})
            if response.status_code == 200:
                text = response.text
                file_id = url.split("/")[-1]
                files.append({"id": file_id, "text": text})
            else:
                print(f"⚠️ Failed to download {url}: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Error downloading {url}: {e}")
    return files

# Load all transcripts
local_files = load_local_files()
remote_files = download_remote_files()
all_files = local_files + remote_files

print(f"📄 Found {len(all_files)} total transcript files (before deduping).")

# -----------------------------
# 🧠 De-duplicate by content hash
# -----------------------------
unique_docs = {}
for f in all_files:
    hash_val = hashlib.sha256(f["text"].encode("utf-8")).hexdigest()
    if hash_val not in unique_docs:
        unique_docs[hash_val] = f
deduped_files = list(unique_docs.values())
print(f"✅ After de-duplication: {len(deduped_files)} unique files remain.")

# -----------------------------
# 🚀 Upload to Pinecone
# -----------------------------
for file in tqdm(deduped_files, desc="Uploading transcripts"):
    text = file["text"]
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]

    for j, chunk in enumerate(chunks):
        chunk_id = f"{file['id']}-{j}"

        # Generate embedding
        emb = openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=chunk
        ).data[0].embedding

        # Upload to Pinecone
        index.upsert([
            {
                "id": chunk_id,
                "values": emb,
                "metadata": {"text": chunk, "source": file["id"]}
            }
        ])

print("\n🎉 Done! All transcripts uploaded to Pinecone successfully (no duplicates).")
