#!/usr/bin/env python3
"""
SRT → Plain Text Converter
---------------------------
Converts YouTube auto-generated .srt subtitle files to clean .txt transcripts.
Handles deduplication of overlapping subtitle lines (common in auto-captions).

Usage:
    python srt_to_txt.py              # Convert all SRT files
    python srt_to_txt.py --dry-run    # Preview without writing
"""

import os
import re
import sys
import argparse
from pathlib import Path

CHANNELS_DIR = Path(__file__).parent / "channels"

# Patterns to strip
TIMESTAMP_RE = re.compile(r'^\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}')
SEQ_NUM_RE = re.compile(r'^\d+$')
MUSIC_RE = re.compile(r'^\[(?:Music|Applause|Laughter|music|applause|laughter)\]$', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')  # HTML-like tags in some SRT files


def srt_to_text(srt_content):
    """Convert SRT content to clean plain text."""
    lines = srt_content.split('\n')
    text_lines = []
    seen = set()  # Deduplicate overlapping auto-caption lines

    for line in lines:
        line = line.strip()

        # Skip empty lines, sequence numbers, timestamps
        if not line:
            continue
        if SEQ_NUM_RE.match(line):
            continue
        if TIMESTAMP_RE.match(line):
            continue
        if MUSIC_RE.match(line):
            continue

        # Strip HTML tags
        line = TAG_RE.sub('', line).strip()
        if not line:
            continue

        # Deduplicate (YouTube auto-subs repeat lines across consecutive entries)
        if line not in seen:
            text_lines.append(line)
            seen.add(line)
        # Clear seen set periodically to allow legitimate repeated phrases
        if len(seen) > 50:
            seen.clear()
            seen.add(line)

    return ' '.join(text_lines)


def process_file(srt_path, dry_run=False):
    """Convert a single SRT file to TXT."""
    txt_path = srt_path.with_suffix('.txt')

    # Skip if .txt already exists
    if txt_path.exists():
        return 'skip'

    try:
        srt_content = srt_path.read_text(encoding='utf-8', errors='ignore')
        text = srt_to_text(srt_content)

        if len(text.split()) < 10:
            return 'empty'

        if dry_run:
            return 'would_convert'

        txt_path.write_text(text, encoding='utf-8')
        return 'converted'

    except Exception as e:
        print(f"  Error: {srt_path.name}: {e}")
        return 'error'


def main():
    parser = argparse.ArgumentParser(description="Convert SRT files to plain text")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--channel", type=str, help="Process single channel (e.g. @ThinkBIGBodybuilding)")
    args = parser.parse_args()

    search_dir = CHANNELS_DIR
    if args.channel:
        search_dir = CHANNELS_DIR / args.channel
        if not search_dir.exists():
            print(f"Channel not found: {search_dir}")
            sys.exit(1)

    srt_files = list(search_dir.rglob("*.srt"))
    total = len(srt_files)
    print(f"\nSRT → TXT Converter")
    print(f"Found {total:,} SRT files in {search_dir}")
    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    converted = skipped = empty = errors = 0

    for i, srt in enumerate(sorted(srt_files), 1):
        result = process_file(srt, dry_run=args.dry_run)
        if result == 'converted' or result == 'would_convert':
            converted += 1
        elif result == 'skip':
            skipped += 1
        elif result == 'empty':
            empty += 1
        elif result == 'error':
            errors += 1

        if i % 1000 == 0:
            channel = srt.parent.name
            print(f"  [{i:,}/{total:,}] {channel} — {converted:,} converted, {skipped:,} skipped")

    print(f"\nDone!")
    print(f"  Converted: {converted:,}")
    print(f"  Skipped (txt exists): {skipped:,}")
    print(f"  Empty/too short: {empty:,}")
    print(f"  Errors: {errors:,}")


if __name__ == "__main__":
    main()
