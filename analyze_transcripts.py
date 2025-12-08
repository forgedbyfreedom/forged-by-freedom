#!/usr/bin/env python3
import os
import glob

root = os.getcwd()

channels = [d for d in os.listdir(root) if d.startswith("@") and os.path.isdir(os.path.join(root, d))]
total_channels = len(channels)
total_files = 0
total_words = 0
channel_stats = {}

for ch in channels:
    path = os.path.join(root, ch)
    files = glob.glob(f"{path}/master_transcript*.txt")
    file_count = len(files)
    total_files += file_count

    ch_words = 0
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
                ch_words += len(text.split())
        except Exception as e:
            print(f"⚠️ Error reading {fpath}: {e}")
    channel_stats[ch] = {"files": file_count, "words": ch_words}
    total_words += ch_words

print("=== 📊 Transcript Summary ===")
print(f"Channels: {total_channels}")
print(f"Episodes: {total_files}")
print(f"Total words: {total_words:,}\n")

print("=== Breakdown by Channel ===")
for ch, stats in sorted(channel_stats.items(), key=lambda x: x[1]["words"], reverse=True):
    print(f"{ch:<30} | {stats['files']} files | {stats['words']:,} words")
import json
from analyze_transcripts import channel_stats, total_files, total_words

stats = {
    "summary": {
        "channels": len(channel_stats),
        "episodes": total_files,
        "total_words": total_words
    },
    "channels": [
        {"name": ch, "episodes": stats["files"], "words": stats["words"]}
        for ch, stats in channel_stats.items()
    ]
}

with open("stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)
