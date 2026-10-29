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
import json
import hashlib
import argparse
from pathlib import Path
from anabolics_vocabulary import correct_transcript, CORRECTIONS

BASE = Path(__file__).parent
CHANNELS_DIR = BASE / "channels"
STATE_FILE = BASE / ".fix_state.json"

# Literal correction keys, lowercased once at import instead of once per key
# per file.
_LOWER_KEYS = [k.lower() for k in CORRECTIONS
               if not (k.startswith('#') or k.startswith('//'))]


def vocab_fingerprint():
    """Hash the vocabulary module so that editing it invalidates the whole
    skip-state and every transcript gets re-processed exactly once."""
    h = hashlib.sha1()
    h.update((BASE / "anabolics_vocabulary.py").read_bytes())
    return h.hexdigest()


def load_state():
    """Return {relpath: sha1} for files already known-clean under the current
    vocabulary. A vocabulary change resets the whole map."""
    try:
        blob = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if blob.get("vocab") != vocab_fingerprint():
        return {}
    return blob.get("files", {})


def save_state(files):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"vocab": vocab_fingerprint(), "files": files}),
                   encoding="utf-8")
    tmp.replace(STATE_FILE)


def count_corrections(original, corrected):
    """Count how many corrections were made.

    original.lower() used to be recomputed inside the loop -- 449 times per
    file, over the whole transcript each time. Hoisted out.
    """
    low = original.lower()
    count = 0
    for wrong in _LOWER_KEYS:
        if wrong in low:
            count += low.count(wrong)
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
    """Process all .txt files in a directory recursively.

    Transcript correction is idempotent: once a file has been corrected, running
    the regex passes over it again produces identical bytes. Doing that for every
    file on every nightly run cost 20-28 minutes and blew the CI job timeout, so
    the corpus never actually got embedded. We now remember the sha1 of each file
    we have already left in its final state and skip it unless the file OR the
    vocabulary changed.
    """
    total_files = 0
    total_corrections = 0
    scanned = 0
    skipped = 0

    state = load_state()
    new_state = dict(state)

    for txt_file in directory.rglob("*.txt"):
        # Skip master transcripts (process those separately)
        if "master_transcript" in txt_file.name:
            continue

        scanned += 1
        try:
            rel = str(txt_file.relative_to(directory))
            digest = hashlib.sha1(txt_file.read_bytes()).hexdigest()
        except Exception as e:
            print(f"  Error reading {txt_file}: {e}")
            continue

        if state.get(rel) == digest:
            skipped += 1
            continue

        corrections = process_file(txt_file, dry_run)
        if corrections > 0:
            total_files += 1
            total_corrections += corrections

        if not dry_run:
            try:
                new_state[rel] = hashlib.sha1(txt_file.read_bytes()).hexdigest()
            except Exception:
                new_state.pop(rel, None)
            # Persist progress every 200 processed files. Without this, a CI
            # step timeout threw away ALL progress (state was only saved at the
            # very end), so every nightly run re-fixed the same files from
            # scratch and timed out again — the backlog could never drain.
            if (scanned - skipped) % 200 == 0:
                try:
                    save_state(new_state)
                except Exception:
                    pass

    if not dry_run:
        # Drop entries for files that no longer exist so the state cannot grow
        # without bound.
        live = set()
        for txt_file in directory.rglob("*.txt"):
            if "master_transcript" in txt_file.name:
                continue
            live.add(str(txt_file.relative_to(directory)))
        new_state = {k: v for k, v in new_state.items() if k in live}
        try:
            save_state(new_state)
        except Exception as e:
            print(f"  Could not write {STATE_FILE.name}: {e}")

    print(f"\nScanned {scanned} files, skipped {skipped} unchanged, "
          f"processed {scanned - skipped}")

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
