#!/usr/bin/env python3
import os
import csv
from glob import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
TRANSCRIPTS_DIR = os.path.join(ROOT, "transcripts")
OUTPUT_CSV = os.path.join(ROOT, "episode_index.csv")

if not os.path.isdir(TRANSCRIPTS_DIR):
    raise RuntimeError(f"Missing transcripts directory: {TRANSCRIPTS_DIR}")

rows = []
episode_id = 1

# Walk all transcript text files recursively
txt_files = glob(os.path.join(TRANSCRIPTS_DIR, "**", "*.txt"), recursive=True)

for path in txt_files:
    rel_path = os.path.relpath(path, TRANSCRIPTS_DIR)
    parts = rel_path.split(os.sep)

    # Channel = top-level folder
    channel = parts[0] if len(parts) > 1 else "unknown"

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().strip()

    if not text:
        continue

    rows.append({
        "episode_id": episode_id,
        "channel": channel,
        "episode_title": os.path.splitext(os.path.basename(path))[0],
        "source_file": rel_path,
        "word_count": len(text.split())
    })

    episode_id += 1

# HARD FAIL if nothing indexed
if not rows:
    raise RuntimeError("No transcript episodes found — episode_index.csv not generated")

# Write CSV
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "episode_id",
            "channel",
            "episode_title",
            "source_file",
            "word_count",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Episode index written: {OUTPUT_CSV}")
print(f"📊 Episodes indexed: {len(rows)}")
