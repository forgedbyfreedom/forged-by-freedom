#!/usr/bin/env python3
"""
🧠 Ultimate Transcript Consolidation + Upload Script
Version: November 2025
Author: ForgedByFreedom

✅ Consolidates all scattered transcript folders (@channel style)
✅ Deduplicates identical transcript files
✅ Builds fresh master_transcript1.txt for each channel
✅ Uploads all masters to OpenAI Assistant storage (no duplicates)
✅ Removes old 'metadata' argument issue
"""

import os
import hashlib
from glob import glob
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --------------------------
# Utility Functions
# --------------------------
def file_md5(filepath):
    """Return MD5 hash of file contents."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# --------------------------
# Step 1: Consolidate & Deduplicate
# --------------------------
def consolidate_transcripts(root_dir):
    print(f"\n📂 Scanning for transcript folders in: {root_dir}")
    channel_dirs = glob(os.path.join(root_dir, "**", "@*"), recursive=True)
    print(f"🔍 Found {len(channel_dirs)} potential channel folders.\n")

    seen_hashes = set()
    cleaned_folders = []

    for channel_dir in channel_dirs:
        if not os.path.isdir(channel_dir):
            continue

        txt_files = [
            f for f in glob(os.path.join(channel_dir, "*.txt"))
            if not f.endswith("master_transcript1.txt")
        ]
        if not txt_files:
            continue

        combined_path = os.path.join(channel_dir, "master_transcript1.txt")

        with open(combined_path, "w", encoding="utf-8") as master:
            for txt_file in sorted(txt_files):
                with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
                    contents = f.read().strip()
                    if not contents:
                        continue
                    md5 = hashlib.md5(contents.encode("utf-8")).hexdigest()
                    if md5 not in seen_hashes:
                        seen_hashes.add(md5)
                        master.write(contents + "\n\n")
                    else:
                        print(f"🧹 Skipped duplicate file: {txt_file}")

        cleaned_folders.append(channel_dir)
        print(f"✅ Built clean master transcript: {combined_path}")

    print(f"\n🎯 Consolidation complete — {len(cleaned_folders)} folders processed.\n")
    return cleaned_folders


# --------------------------
# Step 2: Upload to OpenAI
# --------------------------
def upload_transcripts(cleaned_folders):
    uploaded_count = 0
    seen_filenames = set()

    print("📤 Uploading consolidated transcripts to OpenAI...\n")

    for folder in cleaned_folders:
        master_path = os.path.join(folder, "master_transcript1.txt")
        if not os.path.exists(master_path):
            continue

        filename = os.path.basename(folder) + "_master.txt"
        if filename in seen_filenames:
            print(f"⚠️ Skipping duplicate upload: {filename}")
            continue
        seen_filenames.add(filename)

        try:
            with open(master_path, "rb") as f:
                client.files.create(file=f, purpose="assistants")
            print(f"✅ Uploaded: {master_path}")
            uploaded_count += 1
        except Exception as e:
            print(f"❌ Error uploading {master_path}: {e}")

    print(f"\n🚀 Upload complete — {uploaded_count} transcripts uploaded to OpenAI.\n")


# --------------------------
# Step 3: Full Pipeline Runner
# --------------------------
def main():
    print("\n🧠 Starting full transcript cleanup + upload pipeline...\n")

    repo_root = os.getcwd()

    # Step 1: Consolidate and deduplicate transcripts
    cleaned_folders = consolidate_transcripts(repo_root)

    # Step 2: Upload everything cleanly
    upload_transcripts(cleaned_folders)

    print("✅ All done — all transcripts are now deduplicated, cleaned, and uploaded.\n")


if __name__ == "__main__":
    main()

