#!/usr/bin/env python3
# Run: python3 scripts/check_vector_ids.py --dir path/to/transcripts
import sys
import argparse
import subprocess
import unicodedata
import re
import hashlib
from pathlib import Path

def sanitize_vector_id(name: str, index: int | None = None, max_len: int = 200) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_bytes = normalized.encode("ascii", "ignore")
    ascii_name = ascii_bytes.decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9\._-]+", "-", ascii_name).strip("-")
    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode("utf-8", "surrogatepass")).hexdigest()[:12]
    suffix = f"-{index}" if index is not None else ""
    max_name_len = max_len - len(suffix)
    if len(ascii_name) > max_name_len:
        ascii_name = ascii_name[:max_name_len]
    return ascii_name + suffix

def has_non_ascii(s: str) -> bool:
    return any(ord(c) > 127 for c in s)

def git_tracked_files():
    p = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    if p.returncode != 0:
        print("git ls-files failed; ensure you run this in a git repo", file=sys.stderr)
        sys.exit(2)
    return [Path(x) for x in p.stdout.splitlines() if x.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None, help="Optional directory to restrict scanning")
    ap.add_argument("--show-sanitized", action="store_true", default=True, help="Show sanitized id for each file")
    args = ap.parse_args()

    files = git_tracked_files()
    if args.dir:
        root = Path(args.dir)
        files = [f for f in files if root in f.parents or f == root]

    non_ascii_files = []
    sample_map = []
    for f in files:
        fname = str(f)
        if has_non_ascii(fname):
            non_ascii_files.append(fname)
        if args.show_sanitized:
            sanitized = sanitize_vector_id(Path(fname).name, index=0)
            sample_map.append((fname, sanitized, has_non_ascii(sanitized)))

    if non_ascii_files:
        print("=== Found git-tracked filenames containing non-ASCII characters ===")
        for n in non_ascii_files:
            print(n)
    else:
        print("No git-tracked filenames with non-ASCII characters found.")

    print("\n=== Sample source -> sanitized-id (first 200 entries) ===")
    for src, sid, bad in sample_map[:200]:
        flag = " [BAD]" if bad else ""
        print(f"{src}  ->  {sid}{flag}")

    # Exit with non-zero if any filename is non-ascii OR any sanitized id still contains non-ascii
    bad_sanitized = [sid for (_, sid, bad) in sample_map if bad]
    if non_ascii_files or bad_sanitized:
        print("\nProblems detected. Please either rename source files or ensure code uses sanitize_vector_id before upsert.")
        sys.exit(1)
    else:
        print("\nAll good: sanitized ids are ASCII-only.")
        sys.exit(0)

if __name__ == '__main__':
    main()
