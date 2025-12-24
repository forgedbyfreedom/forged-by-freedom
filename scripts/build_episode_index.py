#!/usr/bin/env python3
import os
import csv
import re
from glob import glob
from pathlib import Path
from dotenv import load_dotenv

# ---------------- ENV ----------------
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# ---------------- PATHS ----------------
ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS_DIR = ROOT / "transcripts"
OUTPUT_CSV = ROOT / "episode_index.csv"

EPISODE_PATTERNS = [
    r"(?:episode|ep\.?)\s*(\d{1,5})",
    r"#\s*(\d{1,5})",
    r"\b(\d{1,5})\b"
]

def extract_episode_number(text: str):
    for p in EPISODE_PATTERNS:
        m = re.search(p, text.lower())
        if m:
            return m.group(1)
    return ""

rows = []
episode_id = 1

for channel_dir in sorted(p for p in TRANSCRIPTS_DIR.iterdir() if p.is_dir()):
    for f in sorted(channel_dir.glob("*.txt")):
        text = f.read_text(errors="ignore")
        title = f.stem

        ep = extract_episode_number(text) or extract_episode_number(title)

        rows.append({
            "episode_id": episode_id,
            "episode_number": ep,
            "episode_title": title,
            "channel": channel_dir.name,
            "source_file": f.name,
            "word_count": len(text.split())
        })

        episode_id += 1

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Episode index built: {OUTPUT_CSV}")
