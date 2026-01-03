#!/usr/bin/env python3
"""
🔥 Forged By Freedom — Master Transcript Builder
------------------------------------------------
Combines all per-episode transcript text files from each @Channel folder
into a single master_transcript1.txt for that channel.

✅ Works locally and inside GitHub Actions
✅ Skips existing master_transcript*.txt files
✅ Automatically handles any number of channels
✅ Adds rebuild timestamp
✅ Splits into master_transcript2.txt, master_transcript3.txt, etc. if file > 95 MB
"""

import os
import sys
from datetime import datetime

# --- Auto-detect repository root (wherever this script lives) ---
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Split threshold in MB ---
MAX_SIZE_MB = 95

def combine_transcripts_for_channel(channel_path: str):
    """Combine all transcript .txt files in a channel directory."""
    txt_files = sorted([
        f for f in os.listdir(channel_path)
        if f.endswith(".txt") and not f.startswith("master_transcript")
    ])

    if not txt_files:
        print(f"⚠️ No transcripts found in {channel_path}")
        return

    output_index = 1
    output_file = os.path.join(channel_path, f"master_transcript{output_index}.txt")
    out = open(output_file, "w", encoding="utf-8")
    current_size = 0

    for fname in txt_files:
        fpath = os.path.join(channel_path, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                header = f"\n\n=== FILE: {fname} ===\n\n"
                out.write(header)
                out.write(f.read())
        except Exception as e:
            print(f"❌ Error reading {fname}: {e}")
            continue

        current_size = os.path.getsize(output_file) / (1024 * 1024)
        if current_size >= MAX_SIZE_MB:
            out.write(f"\n\n=== Split at {current_size:.2f} MB ===\n")
            out.close()
            print(f"📦 Created {output_file} ({current_size:.2f} MB)")
            output_index += 1
            output_file = os.path.join(channel_path, f"master_transcript{output_index}.txt")
            out = open(output_file, "w", encoding="utf-8")
            current_size = 0

    out.write(f"\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")
    out.close()
    print(f"✅ Finished {channel_path}/master_transcript{output_index}.txt\n")


def rebuild_all_channels():
    """Iterate through all @Channel directories and rebuild master transcripts."""
    print("🔧 Starting master transcript rebuild process...\n")
    channel_dirs = [
        d for d in os.listdir(REPO_ROOT)
        if d.startswith("@") and os.path.isdir(os.path.join(REPO_ROOT, d))
    ]

    if not channel_dirs:
        print("⚠️ No @channel directories found — nothing to rebuild.")
        return

    for channel in sorted(channel_dirs):
        ch_path = os.path.join(REPO_ROOT, channel)
        print(f"📘 Building transcripts for {channel}...")
        combine_transcripts_for_channel(ch_path)

    print("🎯 All transcripts rebuilt successfully.\n")


if __name__ == "__main__":
    try:
        rebuild_all_channels()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
