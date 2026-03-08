#!/usr/bin/env python3
"""Fix vocab fixer corruption in CycleDesignGuide files.

The old vocab fixer (before word boundary fix) caused these corruptions:
- "training" -> "trening" (from "train" -> "tren")
- "CHOLESTEROL" -> "CHOLesterOL" (from "ester" -> "ester" case mangling)
- "PROGESTERONE" -> "PROGesterONE"
- "TESTOSTERONE" -> various corruptions with "ester"
- "growth" -> "growth hormone" (triple-applied: "growth hormone hormone hormone")
- "g h" -> "GH" inside words (e.g., "getting high" -> "gettinGHigh")
- "TRANSFERASE" -> "trenSFERASE"
- "transforms" -> "trensforms"
- "trend" -> "tren" (compound name replacing English word)
- "trained" -> "trened"
- "trending" -> "trening"
- Various space-eating corruptions
"""
import re
import sys
from pathlib import Path

CHANNELS_DIR = Path(__file__).parent / "channels" / "@CycleDesignGuide"

# Ordered replacements (most specific first to avoid double-replacing)
FIXES = [
    # Triple/double growth hormone (from "growth" -> "growth hormone" applied multiple times)
    ("growth hormone hormone hormone", "growth hormone"),
    ("growth hormone hormone", "growth hormone"),

    # Ester corruptions inside medical/chemical terms
    ("CHOLesterOL", "CHOLESTEROL"),
    ("cholesterOL", "cholesterol"),
    ("Cholesteresterol", "Cholesterol"),
    ("PROGesterONE", "PROGESTERONE"),
    ("progesterone", "progesterone"),  # may be fine, keep as is
    ("testosterONE", "testosterone"),
    ("TestosterONE", "Testosterone"),
    ("TESTOSTerONE", "TESTOSTERONE"),
    ("trenSFERASE", "TRANSFERASE"),
    ("transferase", "transferase"),  # verify no corruption

    # GH inserted inside words (from "g h" -> "GH" without word boundaries)
    # Match pattern: lowercase letter + "GH" + uppercase or lowercase letter
    # These are specific known corruptions:
    ("runninGH", "running h"),
    ("gettinGH", "getting h"),
    ("beinGH", "being h"),
    ("monitorinGH", "monitoring h"),  # but "monitorinGHGH" -> "monitoring GH"
    ("ongoinGH", "ongoing h"),
    ("RestinGH", "Resting h"),
    ("buildinGH", "building h"),
    ("durinGH", "during h"),
    ("takingGH", "taking h"),
    ("usingGH", "using h"),
    ("doingGH", "doing h"),
    ("havingGH", "having h"),
    ("seeingGH", "seeing h"),
    ("addingGH", "adding h"),
    ("losingGH", "losing h"),
    ("causingGH", "causing h"),
    ("makingGH", "making h"),

    # Train/tren corruptions
    ("trening", "training"),  # most common
    ("trened", "trained"),
    ("trener", "trainer"),
    ("treners", "trainers"),
    ("trensforms", "transforms"),
    ("trensfer", "transfer"),
    ("trensition", "transition"),
    ("trenslate", "translate"),
    ("trensient", "transient"),
    ("trenscript", "transcript"),
    ("trensparency", "transparency"),

    # Space-eating corruptions
    ("arecompletely", "are completely"),
    ("morecomplete", "more complete"),
    ("IMake", "I make"),
]

# Context-dependent fixes (need regex)
REGEX_FIXES = [
    # "monitorinGHGH" -> "monitoring GH" (double GH insertion)
    (r'monitorinGHGH', 'monitoring GH'),
    # "prostate growth hormone" where it should be "prostate growth" (growth was replaced)
    (r'prostate growth hormone(?! (?:hormone|and|is|was|use|dose|at|therapy))', 'prostate growth'),
    # "hair growth hormone" where it should be "hair growth"
    (r'hair growth hormone(?! (?:hormone|and|is|was|use|dose|at|therapy))', 'hair growth'),
    # "muscle growth hormone" where it should be "muscle growth" (context-dependent)
    # Be careful: "muscle growth hormone" could be legitimate if discussing GH for muscle growth
    # Skip this one to be safe
]


def fix_file(filepath):
    """Fix vocab corruption in a single file. Returns (changes_made, details)."""
    text = filepath.read_text(encoding='utf-8')
    original = text
    changes = []

    for old, new in FIXES:
        if old in text:
            count = text.count(old)
            text = text.replace(old, new)
            changes.append(f"  {old} -> {new} ({count}x)")

    for pattern, replacement in REGEX_FIXES:
        matches = re.findall(pattern, text)
        if matches:
            text = re.sub(pattern, replacement, text)
            changes.append(f"  [regex] {pattern} -> {replacement} ({len(matches)}x)")

    if text != original:
        filepath.write_text(text, encoding='utf-8')
        return True, changes
    return False, []


def main():
    txt_files = sorted(CHANNELS_DIR.glob("*.txt"))
    # Skip master transcripts (they'll be rebuilt)
    txt_files = [f for f in txt_files if not f.name.startswith("master_")]

    total_fixed = 0
    for filepath in txt_files:
        changed, details = fix_file(filepath)
        if changed:
            total_fixed += 1
            print(f"FIXED: {filepath.name}")
            for d in details:
                print(d)
            print()
        else:
            print(f"  OK: {filepath.name}")

    print(f"\n{'='*60}")
    print(f"Fixed {total_fixed}/{len(txt_files)} files")

    if total_fixed > 0:
        print("\nRemember to rebuild masters and re-ingest to Pinecone!")


if __name__ == "__main__":
    main()
