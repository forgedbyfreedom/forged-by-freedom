# sync_all_transcripts_to_pinecone.py
# Upload all transcripts (including remote ones) to Pinecone, skipping duplicates.

import os
import requests
import hashlib
from tqdm import tqdm
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# -----------------------------
# 🔑 API Keys
# -----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-your-openai-key")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "pcsk-your-pinecone-key")

# -----------------------------
# ⚙️ Initialize Clients
# -----------------------------
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

INDEX_NAME = "forged-transcripts"

# Create the index if it doesn’t exist
if INDEX_NAME not in [i["name"] for i in pc.list_indexes().indexes]:
    print(f"🪶 Creating Pinecone index: {INDEX_NAME} ...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
index = pc.Index(INDEX_NAME)
print(f"✅ Using Pinecone index: {INDEX_NAME}")

# -----------------------------
# 📂 Gather All Transcript Sources
# -----------------------------
LOCAL_FOLDER = "/Users/weero/forged-by-freedom/transcripts"
REMOTE_FILE_URLS = [
    "https://platform.openai.com/storage/files/file-JanULGgnLMqaG5M2U8Rvt3"  # your remote file
]

def load_local_files():
    files = []
    if os.path.exists(LOCAL_FOLDER):
        for f in os.listdir(LOCAL_FOLDER):
            if f.endswith(".txt"):
                path = os.path.join(LOCAL_FOLDER, f)
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    text = fp.read()
                files.append({"id": f, "text": text})
    return files

def download_remote_files():
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

# Load local and remote transcripts
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
        emb = openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=chunk
        ).data[0].embedding

        index.upsert([
            {
                "id": chunk_id,
                "values": emb,
                "metadata": {"text": chunk, "source": file["id"]}
            }
        ])

print("\n🎉 Done! All transcripts uploaded to Pinecone successfully (no duplicates).")
