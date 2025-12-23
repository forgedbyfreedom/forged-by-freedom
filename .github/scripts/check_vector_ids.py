#!/usr/bin/env python3
import sys
import subprocess
import unicodedata
import re
import hashlib
from pathlib import Path

def sanitize(name, index=0, max_len=200):
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name).strip("-")
    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode()).hexdigest()[:12]
    suffix = f"-{index}"
    return (ascii_name[: max_len - len(suffix)] + suffix)

def has_non_ascii(s):
    return any(ord(c) > 127 for c in s)

p = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
files = p.stdout.splitlines()

bad = False
for f in files:
    sid = sanitize(Path(f).name)
    if has_non_ascii(f) or has_non_ascii(sid):
        print(f"❌ {f} -> {sid}")
        bad = True

if bad:
    sys.exit(1)

print("✅ All vector IDs are ASCII-safe")
