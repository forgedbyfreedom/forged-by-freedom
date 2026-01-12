#!/usr/bin/env python3
"""
🔥 Forged By Freedom — Master Transcript Builder
------------------------------------------------
Combines all per-episode transcript text files from each @Channel folder
into one or more master_transcript*.txt files per channel.

✅ Auto-detects repo root
✅ Works locally & GitHub Actions
✅ Skips existing master_transcript files
✅ Splits files at ~95MB
"""

import os
from datetime import datetime

# -------------------------------------------------
# Correct repo root (ONE LEVEL ABOVE /ingest)
# -------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS_ROOT = os.path.join(REPO_ROOT, "ingest", "channels")
OUTPUT_ROOT = os.path.join(REPO_ROOT, "transcripts")

MAX_SIZE_MB = 95
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


def combine_transcripts_for_channel(channel_path: str):
    channel_name = os.path.basename(channel_path)
    output_dir = os.path.join(OUTPUT_ROOT, channel_name)
    os.makedirs(output_dir, exist_ok=True)

    txt_files = sorted([
        f for f in os.listdir(channel_path)
        if f.endswith(".txt") and not f.startswith("master_transcript")
    ])

    if not txt_files:
        print(f"⚠️  No episode transcripts found for {channel_name}")
        return

    part = 1
    current_size = 0
    buffer = []

    def write_out(part_num, lines):
        outfile = os.path.join(output_dir, f"master_transcript{part_num}.txt")
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(f"MASTER TRANSCRIPT — {channel_name}\n")
            f.write(f"Rebuilt: {datetime.utcnow().isoformat()} UTC\n\n")
            f.write("".join(lines))
        print(f"✅ Wrote {outfile}")

    for filename in txt_files:
        path = os.path.join(channel_path, filename)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        size = len(text.encode("utf-8"))

        if current_size + size > MAX_SIZE_BYTES:
            write_out(part, buffer)
            part += 1
            buffer = []
            current_size = 0

        buffer.append(f"\n\n=== FILE: {filename} ===\n\n")
        buffer.append(text)
        current_size += size

    if buffer:
        write_out(part, buffer)


def main():
    print("\n🔧 Starting master transcript rebuild process...\n")

    if not os.path.isdir(CHANNELS_ROOT):
        print(f"❌ Channel root not found: {CHANNELS_ROOT}")
        return

    channels = [
        d for d in os.listdir(CHANNELS_ROOT)
        if d.startswith("@") and os.path.isdir(os.path.join(CHANNELS_ROOT, d))
    ]

    if not channels:
        print("⚠️ No @channel directories found — nothing to rebuild.")
        return

    for ch in sorted(channels):
        print(f"\n📂 Processing channel: {ch}")
        combine_transcripts_for_channel(os.path.join(CHANNELS_ROOT, ch))

    print("\n🔥 Master transcript rebuild COMPLETE\n")


if __name__ == "__main__":
    main()
