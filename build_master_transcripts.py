#!/usr/bin/env python3
"""
build_master_transcripts.py
--------------------------------
Rebuilds master transcript files for all channels inside the repo.

✅ Automatically detects all @channel directories
✅ Works both locally and in GitHub Actions
✅ Skips master_transcript*.txt files
✅ Logs missing folders instead of crashing
"""

import os
from datetime import datetime

# Use the current working directory (safe for GitHub Actions)
REPO_ROOT = os.getcwd()

def combine_transcripts():
    print(f"🔧 Running in {REPO_ROOT}")

    # Find all directories starting with '@'
    channel_dirs = [
        d for d in os.listdir(REPO_ROOT)
        if d.startswith("@") and os.path.isdir(os.path.join(REPO_ROOT, d))
    ]

    if not channel_dirs:
        print("⚠️ No @channel directories found — nothing to build.")
        return

    for channel in channel_dirs:
        channel_path = os.path.join(REPO_ROOT, channel)
        print(f"📂 Processing channel: {channel}")

        # Find all text transcripts (skip master files)
        txt_files = [
            f for f in os.listdir(channel_path)
            if f.endswith(".txt") and not f.startswith("master_transcript")
        ]

        if not txt_files:
            print(f"⚠️ No transcript files found in {channel}, skipping.")
            continue

        output_path = os.path.join(channel_path, "master_transcript1.txt")

        with open(output_path, "w", encoding="utf-8") as outfile:
            for txt_file in sorted(txt_files):
                file_path = os.path.join(channel_path, txt_file)
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        outfile.write(f"### {txt_file}\n")
                        outfile.write(infile.read())
                        outfile.write("\n\n")
                except Exception as e:
                    print(f"❌ Error reading {file_path}: {e}")

            outfile.write(f"\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")

        print(f"✅ Built {output_path}")

if __name__ == "__main__":
    combine_transcripts()#!/usr/bin/env python3
"""
build_master_transcripts.py
--------------------------------
Rebuilds master transcript files for all channels inside the repo.

✅ Automatically detects all @channel directories
✅ Works both locally and in GitHub Actions
✅ Skips master_transcript*.txt files
✅ Logs missing folders instead of crashing
"""

import os
from datetime import datetime

# Use the current working directory (safe for GitHub Actions)
REPO_ROOT = os.getcwd()

def combine_transcripts():
    print(f"🔧 Running in {REPO_ROOT}")

    # Find all directories starting with '@'
    channel_dirs = [
        d for d in os.listdir(REPO_ROOT)
        if d.startswith("@") and os.path.isdir(os.path.join(REPO_ROOT, d))
    ]

    if not channel_dirs:
        print("⚠️ No @channel directories found — nothing to build.")
        return

    for channel in channel_dirs:
        channel_path = os.path.join(REPO_ROOT, channel)
        print(f"📂 Processing channel: {channel}")

        # Find all text transcripts (skip master files)
        txt_files = [
            f for f in os.listdir(channel_path)
            if f.endswith(".txt") and not f.startswith("master_transcript")
        ]

        if not txt_files:
            print(f"⚠️ No transcript files found in {channel}, skipping.")
            continue

        output_path = os.path.join(channel_path, "master_transcript1.txt")

        with open(output_path, "w", encoding="utf-8") as outfile:
            for txt_file in sorted(txt_files):
                file_path = os.path.join(channel_path, txt_file)
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        outfile.write(f"### {txt_file}\n")
                        outfile.write(infile.read())
                        outfile.write("\n\n")
                except Exception as e:
                    print(f"❌ Error reading {file_path}: {e}")

            outfile.write(f"\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")

        print(f"✅ Built {output_path}")

if __name__ == "__main__":
    combine_transcripts()
#!/usr/bin/env python3
"""
ForgedByFreedom Transcript Builder
---------------------------------
Combines individual transcript text files from each @Channel folder
into a single master_transcript1.txt per channel.

Works both locally and inside GitHub Actions.
"""

import os
import sys
from datetime import datetime

# 🧭 Auto-detect the repo root directory (wherever this script is executed)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

def combine_transcripts():
    print("🔧 Starting transcript rebuild process...\n")

    # Find all folders starting with "@"
    channel_dirs = [
        d for d in os.listdir(REPO_ROOT)
        if d.startswith("@") and os.path.isdir(os.path.join(REPO_ROOT, d))
    ]

    if not channel_dirs:
        print("⚠️ No channel folders found (expected directories like @ThinkBIGBodybuilding).")
        sys.exit(1)

    # Process each channel directory
    for channel in channel_dirs:
        channel_path = os.path.join(REPO_ROOT, channel)
        txt_files = sorted([
            f for f in os.listdir(channel_path)
            if f.endswith(".txt") and not f.startswith("master_transcript")
        ])

        if not txt_files:
            print(f"⚠️ No .txt transcripts found in {channel}/ — skipping.")
            continue

        output_path = os.path.join(channel_path, "master_transcript1.txt")
        print(f"📘 Building master transcript for {channel} ...")

        with open(output_path, "w", encoding="utf-8") as outfile:
            for fname in txt_files:
                fpath = os.path.join(channel_path, fname)
                with open(fpath, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read().strip() + "\n\n")
            outfile.write(f"\n\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")

        print(f"✅ Finished {channel} → {output_path}\n")

    print("🎯 All transcripts combined successfully.")

if __name__ == "__main__":
    try:
        combine_transcripts()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
import os

# ====== CONFIG ======
BASE_DIR = "/Users/weero/thinkbig_podcast/transcripts/@ThinkBIGBodybuilding"
OUTPUT_PREFIX = os.path.join(BASE_DIR, "master_transcript")
MAX_SIZE_MB = 100  # split after each ~100 MB
# ====================

def combine_transcripts():
    txt_files = [os.path.join(BASE_DIR, f) for f in os.listdir(BASE_DIR) if f.endswith(".txt")]
    txt_files.sort(key=os.path.getmtime)  # sort by modified date
    
    if not txt_files:
        print("⚠️ No .txt transcript files found.")
        return

    output_index = 1
    current_size = 0
    output_file = f"{OUTPUT_PREFIX}{output_index}.txt"
    out = open(output_file, "w", encoding="utf-8")

    for file in txt_files:
        with open(file, "r", encoding="utf-8", errors="ignore") as f:
            content = f"\n\n=== {os.path.basename(file)} ===\n\n" + f.read()
            out.write(content)
            current_size = os.path.getsize(output_file) / (1024 * 1024)
            if current_size >= MAX_SIZE_MB:
                out.close()
                print(f"✅ Created {output_file} ({current_size:.2f} MB)")
                output_index += 1
                output_file = f"{OUTPUT_PREFIX}{output_index}.txt"
                out = open(output_file, "w", encoding="utf-8")
                current_size = 0

    out.close()
    print(f"✅ Finished! Last file: {output_file}")

if __name__ == "__main__":
    combine_transcripts()

