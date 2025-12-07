#!/usr/bin/env python3
"""
build_file_index.py
------------------------------------------------------------
Builds a clean, deduplicated JSON index of all transcript files.

✅ Automatically scans /transcripts/ and all @channel folders
✅ Deduplicates using MD5 hashes
✅ Counts token estimates for each transcript
✅ Always writes file_index.json into /transcripts/
✅ Works both locally and inside GitHub Actions
"""

import os
import json
import hashlib
from datetime import datetime

# --- 🧭 Define consistent paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTS_DIR = os.path.join(SCRIPT_DIR, "../../../transcripts")
OUTPUT_FILE = os.path.join(TRANSCRIPTS_DIR, "file_index.json")

index = []
hash_set = set()

print("🧹 Scanning for transcripts in:", TRANSCRIPTS_DIR)

if not os.path.exists(TRANSCRIPTS_DIR):
    print(f"❌ Transcripts directory not found: {TRANSCRIPTS_DIR}")
    exit(1)

# --- 🔍 Recursively walk through transcript folders ---
for root, dirs, files in os.walk(TRANSCRIPTS_DIR):
    for file in files:
        if file.endswith(".txt"):
            path = os.path.join(root, file)

            # Skip generated master transcripts
            if "master_transcript" in file.lower():
                continue

            try:
                with open(path, "rb") as f:
                    data = f.read()
                file_hash = hashlib.md5(data).hexdigest()
            except Exception as e:
                print(f"⚠️ Could not read file {path}: {e}")
                continue

            # Skip duplicates
            if file_hash in hash_set:
                print(f"⚠️ Duplicate detected — skipping: {path}")
                continue

            hash_set.add(file_hash)

            # Estimate token count
            text = data.decode(errors="ignore")
            tokens = len(text.split())

            channel = os.path.basename(os.path.dirname(path))

            index.append({
                "channel": channel,
                "filename": file,
                "relative_path": os.path.relpath(path, TRANSCRIPTS_DIR),
                "tokens": tokens,
                "hash": file_hash,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            })

# --- 💾 Write to file_index.json ---
index.sort(key=lambda x: (x["channel"], x["filename"]))

os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

print(f"\n✅ Indexed {len(index)} unique transcript files.")
print(f"💾 file_index.json written to: {OUTPUT_FILE}")
print("🎯 Index build complete.\n")
