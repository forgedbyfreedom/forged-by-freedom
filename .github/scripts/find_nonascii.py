#!/usr/bin/env python3
import os
import unicodedata
import re
import hashlib
import subprocess
import pathlib
import sys

def sanitize(name, index=None, max_len=200):
    normalized = unicodedata.normalize("NFKD", name)
    ascii_bytes = normalized.encode("ascii", "ignore")
    ascii_name = ascii_bytes.decode("ascii")
    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', '-', ascii_name).strip('-')
    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode('utf-8', 'surrogatepass')).hexdigest()[:12]
    suffix = f'-{index}' if index is not None else ''
    max_name_len = max_len - len(suffix)
    if len(ascii_name) > max_name_len:
        ascii_name = ascii_name[:max_name_len]
    return ascii_name + suffix

def has_non_ascii(s):
    return any(ord(c) > 127 for c in s)

# Configure failsafe marker via environment variable.
# If IGNORE_AFTER is non-empty and appears in a file path, we check only the substring
# after the first occurrence of the marker; if that substring contains non-ASCII,
# the file is ignored (skipped).
IGNORE_AFTER = os.getenv("IGNORE_AFTER", "ggst")  # default "ggst" per your request; set to "" to disable

proc = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)
if proc.returncode != 0:
    print("Failed to run 'git ls-files':", proc.stderr.strip())
    sys.exit(2)

files = [l for l in proc.stdout.splitlines() if l.strip()]
if not files:
    print("No git-tracked files found.")
    sys.exit(0)

ignored_files = []
print(f"=== Failsafe ignore marker: '{IGNORE_AFTER}' (empty to disable) ===")
if IGNORE_AFTER:
    for f in files:
        if IGNORE_AFTER in f:
            tail = f.split(IGNORE_AFTER, 1)[1]
            if has_non_ascii(tail):
                ignored_files.append(f)

if ignored_files:
    print("Files ignored by failsafe (non-ASCII found after marker):")
    for f in ignored_files:
        print("  " + f)
else:
    print("No files ignored by the failsafe.")

print("\n=== Git-tracked files containing non-ASCII characters (if any) ===")
found = False
for f in files:
    if f in ignored_files:
        # explicitly note that the file was ignored
        print(f"{f}  (ignored by failsafe)")
        continue
    if has_non_ascii(f):
        print(f)
        found = True
if not found:
    print("(none)")

print("\n=== Generating sanitized ids for all git-tracked files (sample mapping) ===")
bad_sanitized = []
for f in files:
    if f in ignored_files:
        print(f"{f}  ->  (skipped/ignored by failsafe)")
        continue
    src_name = pathlib.Path(f).name
    sanitized = sanitize(src_name, index=0)
    bad_flag = has_non_ascii(sanitized)
    note = " [BAD]" if bad_flag else ""
    print(f"{f}  ->  {sanitized}{note}")
    if bad_flag:
        bad_sanitized.append((f, sanitized))

if bad_sanitized:
    print()
    print("Found sanitized IDs that still contain non-ASCII characters (unexpected):")
    for f, s in bad_sanitized:
        print(f"  {f} -> {s}")
    sys.exit(1)
else:
    print()
    print("All sanitized IDs are ASCII-only (ignoring files skipped by the failsafe).")
    sys.exit(0)
