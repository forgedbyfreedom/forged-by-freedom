#!/usr/bin/env python3
"""
build_master_transcripts.py
--------------------------------
✅ Rebuilds master_transcript*.txt for all @channel folders
✅ Creates a file_index.json summary for Pinecone ingestion
✅ Works locally and inside GitHub Actions
"""

import os
import json
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
FILE_INDEX_PATH = os.path.join(REPO_ROOT, "file_index.json")


def combine_transcripts(channel_path):
    """
    Combine all .txt files (except master_transcript*) in a given channel directory.
    """
    txt_files = [
        f for f in os.listdir(channel_path)
        if f.endswith(".txt") and not f.startswith("master_transcript")
    ]
    if not txt_files:
        print(f"⚠️ No .txt transcripts found in {channel_path}, skipping.")
        return None

    output_path = os.path.join(channel_path, "master_transcript1.txt")
    with open(output_path, "w", encoding="utf-8") as outfile:
        for fname in sorted(txt_files):
            fpath = os.path.join(channel_path, fname)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as infile:
                outfile.write(f"### {fname}\n")
                outfile.write(infile.read().strip() + "\n\n")
        outfile.write(f"=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")

    print(f"✅ Built {output_path}")
    return output_path


def build_file_index(channels_data):
    """
    Build file_index.json — a summary of all transcripts.
    """
    index_data = []
    for ch, path in channels_data.items():
        if path:
            index_data.append({
                "channel": ch,
                "file": os.path.basename(path),
                "path": path.replace(REPO_ROOT + "/", ""),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })

    with open(FILE_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

    print(f"📚 file_index.json written with {len(index_data)} entries.")


def rebuild_all_channels():
    """
    Automatically rebuild all @channel transcript folders.
    """
    channels_data = {}
    print("🔧 Starting transcript rebuild process...\n")

    for folder in sorted(os.listdir(REPO_ROOT)):
        if folder.startswith("@"):
            folder_path = os.path.join(REPO_ROOT, folder)
            if os.path.isdir(folder_path):
                print(f"📘 Processing {folder}...")
                path = combine_transcripts(folder_path)
                channels_data[folder] = path

    if channels_data:
        build_file_index(channels_data)
    else:
        print("⚠️ No channel folders found.")

    print("\n🎯 Transcript rebuild complete.")


if __name__ == "__main__":
    rebuild_all_channels()
