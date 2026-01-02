#!/usr/bin/env python3
"""
Forged By Freedom – Transcript Rebuilder
----------------------------------------
Pulls per-channel .txt files (local or cloned repo)
Combines them into master transcripts BEFORE ingestion.
"""

import os
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CHANNELS_DIR = os.path.join(REPO_ROOT, "channels")
OUTPUT_DIR = os.path.join(REPO_ROOT, "../output")

MAX_SIZE_MB = 95

def combine_channel_transcripts(channel_name):
    ch_dir = os.path.join(CHANNELS_DIR, channel_name)
    txt_files = sorted([
        f for f in os.listdir(ch_dir)
        if f.endswith(".txt") and not f.startswith("master_transcript")
    ])

    if not txt_files:
        print(f"[WARN] No transcripts found in {channel_name}")
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    index = 1
    out_path = os.path.join(OUTPUT_DIR, f"{channel_name}_master_{index}.txt")
    out = open(out_path, "w", encoding="utf-8")
    cur_size = 0

    for fname in txt_files:
        with open(os.path.join(ch_dir, fname), "r", encoding="utf-8", errors="ignore") as f:
            header = f"\n\n=== FILE: {fname} ===\n\n"
            out.write(header)
            out.write(f.read())

        cur_size = os.path.getsize(out_path) / (1024 * 1024)
        if cur_size >= MAX_SIZE_MB:
            out.write(f"\n=== Split at {cur_size:.2f} MB ===\n")
            out.close()
            index += 1
            out_path = os.path.join(OUTPUT_DIR, f"{channel_name}_master_{index}.txt")
            out = open(out_path, "w", encoding="utf-8")
            cur_size = 0

    out.write(f"\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")
    out.close()
    return out_path


def main():
    print("🔧 Rebuilding master transcript sets...")
    channels = [d for d in os.listdir(CHANNELS_DIR) if d.startswith("@")]
    results = []

    for channel in channels:
        print(f"📘 Building: {channel}")
        path = combine_channel_transcripts(channel)
        if path:
            results.append(path)

    print("🎯 Done.")
    return results

if __name__ == "__main__":
    main()
