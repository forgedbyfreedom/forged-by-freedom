#!/usr/bin/env python3
"""
build_index.py — Universal Transcript Index Builder for ForgedByFreedom

✅ Scans all transcript folders (@channel)
✅ Deduplicates based on MD5 hash
✅ Builds /transcripts/file_index.json
✅ Outputs summary stats for CI logs
"""

import os, json, hashlib
from datetime import datetime

# 🧭 Repo-relative paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSCRIPTS_DIR = os.path.join(REPO_ROOT, "transcripts")
INDEX_PATH = os.path.join(TRANSCRIPTS_DIR, "file_index.json")

index = []
hash_set = set()

print("🧹 Scanning transcripts directory...\n")

for root, dirs, files in os.walk(TRANSCRIPTS_DIR):
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
                "relative_path": os.path.relpath(path, REPO_ROOT),
                "tokens": tokens,
                "hash": file_hash,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            })

print(f"\n✅ Indexed {len(index)} unique transcripts across all channels.")

os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
with open(INDEX_PATH, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

print(f"💾 file_index.json written successfully to {INDEX_PATH}")

# 🧮 Simple summary output for CI or manual review
channels = sorted(set([x["channel"] for x in index]))
print(f"\n📊 Channels indexed: {len(channels)}")
print(f"📘 Total tokens counted: {sum(x['tokens'] for x in index):,}")
