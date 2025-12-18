#!/usr/bin/env python3

import os
import csv
import re
from glob import glob

# --------------------------------------------------
# Paths
# --------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
TRANSCRIPTS_DIR = os.path.join(ROOT, "transcripts")
OUTPUT_CSV = os.path.join(ROOT, "episode_index.csv")

# --------------------------------------------------
# Regex patterns for episode number detection
# (text first, then title fallback)
# --------------------------------------------------
EPISODE_PATTERNS = [
    r"(?:episode|ep\.?)\s*(\d{1,5})",
    r"#\s*(\d{1,5})",
    r"\b(\d{1,5})\b"
]

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def extract_episode_number(text: str):
    if not text:
        return ""

    text_lower = text.lower()
    for pattern in EPISODE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1)
    return ""

def safe_read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

# --------------------------------------------------
# Build index
# --------------------------------------------------
rows = []
episode_counter = 1

channel_dirs = [
    os.path.join(TRANSCRIPTS_DIR, d)
    for d in os.listdir(TRANSCRIPTS_DIR)
    if os.path.isdir(os.path.join(TRANSCRIPTS_DIR, d))
]

for channel_path in sorted(channel_dirs):
    channel = os.path.basename(channel_path)

    transcript_files = sorted(glob(os.path.join(channel_path, "*.txt")))

    for file_path in transcript_files:
        filename = os.path.basename(file_path)
        title = os.path.splitext(filename)[0]

        transcript_text = safe_read(file_path)

        # Prefer episode number from transcript body
        episode_number = extract_episode_number(transcript_text)

        # Fallback to title if not found
        if not episode_number:
            episode_number = extract_episode_number(title)

        word_count = len(transcript_text.split()) if transcript_text else 0

        rows.append({
            "episode_id": episode_counter,              # stable numeric ID for Wix
            "episode_number": episode_number,           # real podcast number (if found)
            "episode_title": title,
            "channel": channel,
            "source_file": filename,
            "word_count": word_count
        })

        episode_counter += 1

# --------------------------------------------------
# Write CSV (Wix-safe)
# --------------------------------------------------
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = [
        "episode_id",
        "episode_number",
        "episode_title",
        "channel",
        "source_file",
        "word_count"
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("=== 📄 Episode Index Built ===")
print(f"Episodes indexed: {len(rows)}")
print(f"Saved to: {OUTPUT_CSV}")
