import os
from datetime import datetime

# ============================================================
# ✅ UNIVERSAL TRANSCRIPT BUILDER — CI SAFE
# Works on macOS, Linux (GitHub Actions), and local runs.
# ============================================================

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CHANNEL_PREFIX = "@"

def combine_transcripts(base_dir, output_filename="master_transcript1.txt"):
    """Combine all .txt files in a channel directory."""
    if not os.path.exists(base_dir):
        print(f"❌ Directory not found: {base_dir}")
        return

    txt_files = [f for f in os.listdir(base_dir) if f.endswith(".txt")]
    if not txt_files:
        print(f"⚠️ No .txt files found in {base_dir}")
        return

    output_path = os.path.join(base_dir, output_filename)
    with open(output_path, "w") as outfile:
        for fname in sorted(txt_files):
            fpath = os.path.join(base_dir, fname)
            with open(fpath, "r") as infile:
                outfile.write(infile.read())
                outfile.write("\n\n")
        outfile.write(f"\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")
    print(f"✅ Built {output_path}")

def main():
    for folder in os.listdir(REPO_ROOT):
        if folder.startswith(CHANNEL_PREFIX):
            base_dir = os.path.join(REPO_ROOT, folder)
            combine_transcripts(base_dir)

if __name__ == "__main__":
    print("🔧 Starting transcript rebuild process...")
    main()
    print("🎯 All transcripts combined successfully.")
import os
from datetime import datetime

# ============================================================
# ✅ UNIVERSAL TRANSCRIPT BUILDER
# Works on both macOS and GitHub Actions (Linux)
# No hard-coded paths — auto-detects repo structure.
# ============================================================

# --- 🔧 Define repo root dynamically ---
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTS_DIR = REPO_ROOT  # all @channel folders are here

def combine_transcripts(base_dir, output_filename="master_transcript1.txt"):
    """
    Combines all .txt files in a channel directory into one master transcript.
    """
    if not os.path.exists(base_dir):
        print(f"❌ Directory not found: {base_dir}")
        return

    txt_files = [
        os.path.join(base_dir, f)
        for f in os.listdir(base_dir)
        if f.endswith(".txt") and f != output_filename
    ]

    if not txt_files:
        print(f"⚠️ No .txt files found in {base_dir}")
        return

    output_path = os.path.join(base_dir, output_filename)
    print(f"🧩 Combining {len(txt_files)} transcript files → {output_path}")

    with open(output_path, "w", encoding="utf-8") as outfile:
        for file in sorted(txt_files):
            outfile.write(f"\n\n===== FILE: {os.path.basename(file)} =====\n\n")
            with open(file, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())

        outfile.write(f"\n\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")

    print(f"✅ Finished building {output_path}")


def rebuild_all_channels():
    """
    Automatically rebuilds every @channel folder in the repo.
    """
    print("🔧 Starting transcript rebuild process...\n")

    # Iterate over all directories in repo
    for folder in os.listdir(TRANSCRIPTS_DIR):
        if folder.startswith("@"):  # only process channel folders
            folder_path = os.path.join(TRANSCRIPTS_DIR, folder)

            if not os.path.isdir(folder_path):
                continue

            print(f"📘 Building master transcript for {folder} ...")
            try:
                combine_transcripts(folder_path)
                print(f"✅ Finished {folder} → {folder_path}/master_transcript1.txt\n")
            except Exception as e:
                print(f"❌ Error processing {folder}: {e}\n")

    print("🎯 All transcripts combined successfully.\n")


if __name__ == "__main__":
    rebuild_all_channels()
import os
from datetime import datetime

# ============================================================
# ✅ UNIVERSAL TRANSCRIPT BUILDER
# Works on both macOS and GitHub Actions (Linux)
# No hard-coded paths — auto-detects repo structure.
# ============================================================

# --- 🔧 Define repo root dynamically ---
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTS_DIR = REPO_ROOT  # all @channel folders are here

def combine_transcripts(base_dir, output_filename="master_transcript1.txt"):
    """
    Combines all .txt files in a channel directory into one master transcript.
    """
    if not os.path.exists(base_dir):
        print(f"❌ Directory not found: {base_dir}")
        return

    txt_files = [
        os.path.join(base_dir, f)
        for f in os.listdir(base_dir)
        if f.endswith(".txt") and f != output_filename
    ]

    if not txt_files:
        print(f"⚠️ No .txt files found in {base_dir}")
        return

    output_path = os.path.join(base_dir, output_filename)
    print(f"🧩 Combining {len(txt_files)} transcript files → {output_path}")

    with open(output_path, "w", encoding="utf-8") as outfile:
        for file in sorted(txt_files):
            outfile.write(f"\n\n===== FILE: {os.path.basename(file)} =====\n\n")
            with open(file, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())

        outfile.write(f"\n\n=== Rebuilt on {datetime.utcnow().isoformat()}Z ===\n")

    print(f"✅ Finished building {output_path}")


def rebuild_all_channels():
    """
    Automatically rebuilds every @channel folder in the repo.
    """
    print("🔧 Starting transcript rebuild process...\n")

    # Iterate over all directories in repo
    for folder in os.listdir(TRANSCRIPTS_DIR):
        if folder.startswith("@"):  # only process channel folders
            folder_path = os.path.join(TRANSCRIPTS_DIR, folder)

            if not os.path.isdir(folder_path):
                continue

            print(f"📘 Building master transcript for {folder} ...")
            try:
                combine_transcripts(folder_path)
                print(f"✅ Finished {folder} → {folder_path}/master_transcript1.txt\n")
            except Exception as e:
                print(f"❌ Error processing {folder}: {e}\n")

    print("🎯 All transcripts combined successfully.\n")


if __name__ == "__main__":
    rebuild_all_channels()
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

