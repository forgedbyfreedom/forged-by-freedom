#!/usr/bin/env python3
"""
Post-process transcripts to fix common ASR misrecognitions
of anabolic/fitness terminology.

Usage:
    python fix_transcripts.py                    # Fix all transcripts
    python fix_transcripts.py --dry-run          # Preview changes
    python fix_transcripts.py --file path.txt    # Fix single file
"""

import os
import sys
import argparse
from pathlib import Path
from anabolics_vocabulary import correct_transcript, CORRECTIONS

CHANNELS_DIR = Path(__file__).parent / "channels"


def count_corrections(original, corrected):
    """Count how many corrections were made."""
    count = 0
    for wrong in CORRECTIONS.keys():
        if wrong.lower() in original.lower():
            count += original.lower().count(wrong.lower())
    return count


def process_file(filepath, dry_run=False):
    """Process a single transcript file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            original = f.read()
    except Exception as e:
        print(f"  ❌ Error reading {filepath}: {e}")
        return 0

    corrected = correct_transcript(original)

    if original == corrected:
        return 0

    corrections = count_corrections(original, corrected)

    if dry_run:
        print(f"  📝 Would fix {corrections} terms in {filepath.name}")
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(corrected)
        print(f"  ✅ Fixed {corrections} terms in {filepath.name}")

    return corrections


def process_directory(directory, dry_run=False):
    """Process all .txt files in a directory recursively."""
    total_files = 0
    total_corrections = 0

    for txt_file in directory.rglob("*.txt"):
        # Skip master transcripts (process those separately)
        if "master_transcript" in txt_file.name:
            continue

        corrections = process_file(txt_file, dry_run)
        if corrections > 0:
            total_files += 1
            total_corrections += corrections

    return total_files, total_corrections


def main():
    parser = argparse.ArgumentParser(
        description="Fix ASR misrecognitions in transcripts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process a single file instead of all transcripts"
    )
    parser.add_argument(
        "--rebuild-masters",
        action="store_true",
        help="Also rebuild master transcripts after fixing"
    )

    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN - No files will be modified\n")

    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
        process_file(filepath, args.dry_run)
    else:
        print(f"📂 Processing transcripts in {CHANNELS_DIR}\n")

        files, corrections = process_directory(CHANNELS_DIR, args.dry_run)

        print(f"\n{'Would fix' if args.dry_run else 'Fixed'} {corrections} terms across {files} files")

        if args.rebuild_masters and not args.dry_run:
            print("\n🔄 Rebuilding master transcripts...")
            os.system("python build_master_transcripts.py")


if __name__ == "__main__":
    main()
