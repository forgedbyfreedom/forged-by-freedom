#!/usr/bin/env python3
"""
analyze_full_stats.py
--------------------------------
Scans all @channel transcript folders and Pinecone index
to build a full database summary (channels, episodes, words, vectors, size).

Outputs:
  📄 stats.json  — used by your website header or dashboard
"""

import os, glob, json
from datetime import datetime

# Optional: import Pinecone client if available
try:
    from pinecone import Pinecone, ServerlessSpec
except ImportError:
    Pinecone = None

# === CONFIG ===
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "forgedbyfreedom")
ROOT = os.getcwd()

# === SCAN TRANSCRIPTS ===
channels = [d for d in os.listdir(ROOT) if d.startswith("@") and os.path.isdir(os.path.join(ROOT, d))]
channel_stats = {}
total_files = total_words = 0

print(f"🔍 Scanning {len(channels)} channels...\n")

for ch in sorted(channels):
    path = os.path.join(ROOT, ch)
    files = glob.glob(f"{path}/master_transcript*.txt")
    file_count = len(files)
    total_files += file_count

    word_count = 0
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                word_count += len(f.read().split())
        except Exception as e:
            print(f"⚠️ Error reading {fpath}: {e}")
    channel_stats[ch] = {"files": file_count, "words": word_count}
    total_words += word_count

# === OPTIONAL: PINECONE INDEX STATS ===
vector_count = 0
storage_size_gb = 0
if PINECONE_API_KEY and Pinecone:
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX)
        stats = index.describe_index_stats()
        vector_count = stats.get("total_vector_count", 0)
        dim = stats.get("dimension", 1536)
        storage_size_gb = round(vector_count * dim * 4 / 1e9, 2)
    except Exception as e:
        print(f"⚠️ Pinecone connection failed: {e}")
else:
    print("ℹ️ Pinecone stats skipped (no key or client).")

# === BUILD FINAL stats.json ===
stats_json = {
    "summary": {
        "channels": len(channels),
        "episodes": total_files,
        "total_words": total_words,
        "pinecone_vectors": vector_count,
        "pinecone_storage_gb": storage_size_gb,
        "updated": datetime.utcnow().isoformat() + "Z"
    },
    "channels": [
        {"name": ch, "episodes": s['files'], "words": s['words']}
        for ch, s in channel_stats.items()
    ]
}

with open("stats.json", "w", encoding="utf-8") as f:
    json.dump(stats_json, f, indent=2)

print("\n=== 📊 FORGED BY FREEDOM DATABASE STATS ===")
print(f"Channels: {stats_json['summary']['channels']}")
print(f"Episodes: {stats_json['summary']['episodes']}")
print(f"Total Words: {stats_json['summary']['total_words']:,}")
print(f"Pinecone Vectors: {stats_json['summary']['pinecone_vectors']:,}")
print(f"Vector Storage: {stats_json['summary']['pinecone_storage_gb']} GB")
print(f"Updated: {stats_json['summary']['updated']}")
print("===========================================")
print("\n✅ stats.json written successfully.\n")
