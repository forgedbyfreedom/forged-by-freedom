#!/usr/bin/env python3
import sys
import subprocess
import unicodedata
import re
import hashlib
from pathlib import Path

def sanitize(name, index=None, max_len=200):
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name).strip("-")
    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode()).hexdigest()[:12]
    suffix = f"-{index}" if index is not None else ""
    return ascii_name[: max_len - len(suffix)] + suffix

def has_non_ascii(s):
    return any(ord(c) > 127 for c in s)

proc = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
files = proc.stdout.splitlines()

bad = False
for f in files:
    if has_non_ascii(f):
        print(f"❌ Non-ASCII filename: {f}")
        bad = True

if bad:
    sys.exit(1)

print("✅ All vector IDs safe")
