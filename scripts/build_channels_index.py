#!/usr/bin/env python3
import os
import json
from glob import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE_DIR, "..")
TRANSCRIPTS_DIR = os.path.join(ROOT, "transcripts")
CHANNEL_LIST_PATH = os.path.join(BASE_DIR, "channel_list.json")
OUTPUT_PATH = os.path.join(ROOT, "transcripts_summary.json")

with open(CHANNEL_LIST_PATH, "r", encoding="utf-8") as f:
    channels_data = json.load(f)

channel_folders = []
for group in channels_data:
    for ch in group["channels"]:
        folder = os.path.join(TRANSCRIPTS_DIR, ch)
        channel_folders.append(folder)
        os.makedirs(folder, exist_ok=True)

total_channels = len(channel_folders)
total_files = 0
total_words = 0
stats = []

for folder in channel_folders:
    txt_files = glob(os.path.join(folder, "*.txt"))
    episode_count = len(txt_files)
    word_count = 0
    for fpath in txt_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                word_count += len(f.read().split())
        except Exception:
            continue
    stats.append({
        "channel": os.path.basename(folder),
        "episodes": episode_count,
        "words": word_count
    })
    total_files += episode_count
    total_words += word_count

summary = {
    "summary": {
        "channels": total_channels,
        "episodes": total_files,
        "total_words": total_words
    },
    "channels": stats
}

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("=== 📊 Forged By Freedom Transcript Summary ===")
print(f"Channels: {total_channels}")
print(f"Episodes: {total_files}")
print(f"Total Words: {total_words:,}")
print(f"✅ Saved summary to {OUTPUT_PATH}")
