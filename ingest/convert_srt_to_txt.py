#!/usr/bin/env python3
"""
Convert SRT subtitle files to clean searchable TXT files.
Removes timestamps and formatting, applies vocabulary corrections.

Usage:
    python convert_srt_to_txt.py                    # Convert all SRT files
    python convert_srt_to_txt.py --channel @Name   # Convert specific channel
"""

import re
import os
import argparse
from pathlib import Path
from anabolics_vocabulary import correct_transcript

CHANNELS_DIR = Path(__file__).parent / "channels"


def clean_srt(content: str) -> str:
    """Remove SRT formatting, keep only text."""
    lines = []

    for line in content.split('\n'):
        line = line.strip()

        # Skip sequence numbers (just digits)
        if re.match(r'^\d+$', line):
            continue

        # Skip timestamp lines
        if re.match(r'\d{2}:\d{2}:\d{2}', line):
            continue

        # Skip empty lines
        if not line:
            continue

        # Remove HTML-style tags
        line = re.sub(r'<[^>]+>', '', line)

        # Remove speaker labels like "[Music]" or "(applause)"
        line = re.sub(r'\[[^\]]*\]', '', line)
        line = re.sub(r'\([^)]*\)', '', line)

        # Clean up whitespace
        line = ' '.join(line.split())

        if line:
            lines.append(line)

    # Join and deduplicate consecutive duplicates (common in auto-captions)
    text = ' '.join(lines)

    # Remove repeated phrases (auto-caption artifact)
    words = text.split()
    cleaned = []
    prev_phrase = ""

    for i in range(0, len(words), 3):
        phrase = ' '.join(words[i:i+3])
        if phrase != prev_phrase:
            cleaned.extend(words[i:i+3])
        prev_phrase = phrase

    return ' '.join(cleaned)


def convert_file(srt_path: Path, delete_srt: bool = False) -> bool:
    """Convert a single SRT file to TXT."""
    txt_path = srt_path.with_suffix('.txt')

    # Skip if TXT already exists
    if txt_path.exists():
        return False

    try:
        content = srt_path.read_text(encoding='utf-8', errors='ignore')
        clean_text = clean_srt(content)

        # Apply vocabulary corrections
        clean_text = correct_transcript(clean_text)

        # Only save if we have meaningful content
        if len(clean_text.split()) < 50:
            print(f"  ⚠️  Skipping {srt_path.name} - too short ({len(clean_text.split())} words)")
            return False

        txt_path.write_text(clean_text, encoding='utf-8')
        print(f"  ✅ {srt_path.name} → {txt_path.name} ({len(clean_text.split())} words)")

        if delete_srt:
            srt_path.unlink()

        return True

    except Exception as e:
        print(f"  ❌ Error converting {srt_path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert SRT to searchable TXT")
    parser.add_argument("--channel", help="Specific channel to convert")
    parser.add_argument("--delete", action="store_true", help="Delete SRT after conversion")
    args = parser.parse_args()

    if args.channel:
        search_dir = CHANNELS_DIR / args.channel
    else:
        search_dir = CHANNELS_DIR

    print(f"\n{'='*60}")
    print("SRT TO TXT CONVERTER")
    print(f"{'='*60}")
    print(f"Searching: {search_dir}")

    srt_files = list(search_dir.rglob("*.srt"))
    print(f"Found {len(srt_files)} SRT files\n")

    converted = 0
    skipped = 0

    for srt in srt_files:
        if convert_file(srt, args.delete):
            converted += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"COMPLETE: {converted} converted, {skipped} skipped")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
