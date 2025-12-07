#!/usr/bin/env python3
"""
index_transcripts.py — Universal Index Builder for ForgedByFreedom

✅ Scans all transcript folders (like @ThinkBIGBodybuilding)
✅ Deduplicates based on MD5 hash
✅ Builds file_index.json with metadata for Pinecone + OpenAI Assistant
✅ Ignores any files inside .github/
"""

import os, json, hashlib
from datetime import datetime

# 🧭 Detect the correct root (repo root)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(REPO_ROOT, "file_index.json")

index = []
hash_set = set()

print("🧹 Scanning repository for transcripts...\n")

for root, dirs, files in os.walk(REPO_ROOT):
    # Skip GitHub system folders
    if ".github" in root or "__pycache__" in root:
        continue

    for file in files:
        if file.endswith(".txt") and not file.startswith("README"):
            path = os.path.join(root, file)
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except Exception as e:
                print(f"⚠️ Could not read {path}: {e}")
                continue

            file_hash = hashlib.md5(data).hexdigest()
            if file_hash in hash_set:
                print(f"⚠️ Duplicate found, skipping: {path}")
                continue

            hash_set.add(file_hash)
            tokens = len(data.decode(errors="ignore").split())
            channel = os.path.basename(os.path.dirname(path))

            index.append({
                "channel": channel,
                "filename": file,
                "relative_path": path.replace(REPO_ROOT, "").lstrip("/"),
                "tokens": tokens,
                "hash": file_hash,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            })

print(f"\n✅ Indexed {len(index)} unique transcripts.")

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

print(f"💾 file_index.json written successfully at {INDEX_PATH}")
