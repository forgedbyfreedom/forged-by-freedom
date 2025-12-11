#!/usr/bin/env python3
"""
generate_site_stats.py
────────────────────────────
Reads transcripts folder, counts total words, episodes, and channels,
and generates stats.json + transcripts_summary.json for the AI Coach page.
"""

import os, json
from datetime import datetime

TRANSCRIPTS_DIR = "transcripts"
STATS_PATH = os.path.join(TRANSCRIPTS_DIR, "stats.json")
SUMMARY_PATH = os.path.join(TRANSCRIPTS_DIR, "transcripts_summary.json")

summary = {}
total_words = 0
total_episodes = 0

for root, _, files in os.walk(TRANSCRIPTS_DIR):
    if "master_transcript.txt" in root:
        continue
    txt_files = [f for f in files if f.endswith(".txt")]
    if not txt_files:
        continue
    channel = os.path.basename(root)
    summary[channel] = {"episodes": 0, "words": 0}
    for f in txt_files:
        path = os.path.join(root, f)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                text = file.read()
                words = len(text.split())
                summary[channel]["episodes"] += 1
                summary[channel]["words"] += words
                total_episodes += 1
                total_words += words
        except Exception as e:
            print(f"⚠️ Error reading {path}: {e}")

# Write summary per channel
with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

# Write global stats
stats = {
    "total_channels": len(summary),
    "total_episodes": total_episodes,
    "total_words": total_words,
    "last_updated": datetime.now().isoformat(),
}
with open(STATS_PATH, "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)

print(f"✅ Stats updated: {STATS_PATH}")
print(f"📊 {stats}")
