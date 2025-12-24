#!/usr/bin/env python3
import os
import json
from glob import glob
from pathlib import Path
from dotenv import load_dotenv

# ---------------- ENV ----------------
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# ---------------- PATHS ----------------
ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS_DIR = ROOT / "transcripts"
OUTPUT_PATH = TRANSCRIPTS_DIR / "channels_summary.json"

if not TRANSCRIPTS_DIR.is_dir():
    raise RuntimeError(f"Missing transcripts directory: {TRANSCRIPTS_DIR}")

# ---------------- INDEX ----------------
channels = []
total_words = 0
total_files = 0

for folder in sorted(p for p in TRANSCRIPTS_DIR.iterdir() if p.is_dir()):
    txt_files = list(folder.glob("*.txt"))
    words = 0

    for f in txt_files:
        try:
            words += len(f.read_text(errors="ignore").split())
        except Exception:
            continue

    channels.append({
        "channel": folder.name,
        "episodes": len(txt_files),
        "words": words
    })

    total_files += len(txt_files)
    total_words += words

summary = {
    "summary": {
        "channels": len(channels),
        "episodes": total_files,
        "total_words": total_words
    },
    "channels": channels
}

OUTPUT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

print("✅ Channel summary written:", OUTPUT_PATH)
