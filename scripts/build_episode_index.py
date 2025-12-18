#!/usr/bin/env python3
import os
import re
import json
import csv
from glob import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE_DIR, "..")
TRANSCRIPTS_DIR = os.path.join(ROOT, "transcripts")

OUT_JSON = os.path.join(ROOT, "episode_index.json")
OUT_CSV  = os.path.join(ROOT, "episode_index.csv")

EPISODE_MARKER = re.compile(
    r"(?im)^(?:episode\s+\d+|ep\.\s*\d+|#{1,3}\s+.+|={3,}.+)$"
)

rows = []
episode_id = 1

for channel in os.listdir(TRANSCRIPTS_DIR):
    channel_path = os.path.join(TRANSCRIPTS_DIR, channel)
    if not os.path.isdir(channel_path):
        continue

    for fpath in glob(os.path.join(channel_path, "*.txt")):
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        splits = EPISODE_MARKER.split(text)
        if len(splits) <= 1:
            # single-episode file
            words = len(text.split())
            rows.append({
                "episode_id": episode_id,
                "channel": channel,
                "episode_title": os.path.basename(fpath),
                "source_file": os.path.relpath(fpath, ROOT),
                "word_count": words
            })
            episode_id += 1
        else:
            # multi-episode file
            for chunk in splits:
                chunk = chunk.strip()
                if len(chunk.split()) < 200:
                    continue
                rows.append({
                    "episode_id": episode_id,
                    "channel": channel,
                    "episode_title": f"{os.path.basename(fpath)} (segment)",
                    "source_file": os.path.relpath(fpath, ROOT),
                    "word_count": len(chunk.split())
                })
                episode_id += 1

# write JSON
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2)

# write CSV
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["episode_id", "channel", "episode_title", "source_file", "word_count"]
    )
    writer.writeheader()
    writer.writerows(rows)

print("✅ Episode index built")
print(f"Episodes indexed: {len(rows)}")
print(f"JSON → {OUT_JSON}")
print(f"CSV  → {OUT_CSV}")
