#!/usr/bin/env python3
import os
import csv
from glob import glob

# -------------------------------
# Paths
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
TRANSCRIPTS_DIR = os.path.join(ROOT, "transcripts")
OUTPUT_CSV = os.path.join(ROOT, "episode_index.csv")

if not os.path.isdir(TRANSCRIPTS_DIR):
    raise RuntimeError(f"Missing transcripts directory: {TRANSCRIPTS_DIR}")

# -------------------------------
# Build index
# -------------------------------
rows = []
episode_id = 1

for root, dirs, files in os.walk(TRANSCRIPTS_DIR):
    for fname in files:
        if not fname.lower().endswith(".txt"):
            continue

        fpath = os.path.join(root, fname)
        rel_path = os.path.relpath(fpath, TRANSCRIPTS_DIR)

        channel = rel_path.split(os.sep)[0]

        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                word_count = len(f.read().split())
        except Exception:
            word_count = 0

        rows.append({
            "episode_id": episode_id,
            "channel": channel,
            "episode_title": os.path.splitext(fname)[0],
            "source_path": rel_path,
            "word_count": word_count
        })

        episode_id += 1

# -------------------------------
# Write CSV
# -------------------------------
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "episode_id",
            "channel",
            "episode_title",
            "source_path",
            "word_count"
        ]
    )
    writer.writeheader()
    writer.writerows(rows)

print("=== 🔍 Episode Index Built ===")
print(f"Episodes indexed: {len(rows)}")
print(f"CSV written to: {OUTPUT_CSV}")
