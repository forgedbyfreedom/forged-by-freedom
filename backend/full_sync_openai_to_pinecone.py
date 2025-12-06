#!/usr/bin/env python3
"""
Full OpenAI → Pinecone sync (self-healing version).
This version ensures the correct Pinecone SDK is installed even if GitHub Actions preloads `pinecone-client`.
"""

import os, subprocess, sys, importlib, time, json
from pathlib import Path
from tqdm import tqdm

# 🧹 Step 1. Force-install correct Pinecone SDK
def ensure_pinecone():
    try:
        import pinecone
        # verify this is the correct SDK
        if hasattr(pinecone, "Pinecone"):
            print("✅ Correct Pinecone SDK already installed")
            return
        else:
            raise ImportError("Wrong pinecone package")
    except Exception:
        print("⚙️ Installing latest official Pinecone SDK ...")
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "pinecone-client"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--upgrade", "pinecone"],
            check=True,
        )
        importlib.invalidate_caches()
        print("✅ Pinecone SDK fixed")

ensure_pinecone()

# 🧠 Step 2. Import correct SDKs
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI

# 🧩 Step 3. Environment
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

# 🧠 Step 4. Load transcripts
transcripts_dir = Path("transcripts")
files = list(transcripts_dir.glob("*.txt"))
print(f"📚 Found {len(files)} transcript files to sync")

# 🧩 Step 5. Upload each transcript
for file_path in tqdm(files, desc="Uploading transcripts"):
    text = file_path.read_text(errors="ignore")
    metadata = {"filename": file_path.name}
    vector = client.embeddings.create(input=text, model="text-embedding-3-large").data[0].embedding
    index.upsert(vectors=[{"id": file_path.stem, "values": vector, "metadata": metadata}])

print("✅ Pinecone sync complete!")
