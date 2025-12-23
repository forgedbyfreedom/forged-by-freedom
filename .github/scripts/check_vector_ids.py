#!/usr/bin/env python3
import argparse
import subprocess
import unicodedata
import re
import hashlib
from pathlib import Path
import sys

def sanitize_vector_id(name: str, index=None, max_len=200):
    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name).strip("-")

    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode()).hexdigest()[:12]

    suffix = f"-{index}" if index is not None else ""
    return (ascii_name[:max_len - len(suffix)] + suffix)

def has_non_ascii(s: str):
    return any(ord(c) > 127 for c in s)

def git_files():
    p = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit("git ls-files failed")
    return [Path(x) for x in p.stdout.splitlines() if x.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None)
    args = ap.parse_args()

    files = git_files()
    if args.dir:
        root = Path(args.dir)
        files = [f for f in files if root in f.parents]

    bad = False
    for f in files:
        sid = sanitize_vector_id(f.name, 0)
        if has_non_ascii(sid):
            print(f"❌ BAD ID: {f} -> {sid}")
            bad = True

    if bad:
        sys.exit(1)

    print("✅ All vector IDs safe")

if __name__ == "__main__":
    main()
