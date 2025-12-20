#!/usr/bin/env python3
import os
from glob import glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def count_txt(path: str) -> int:
    return len(glob(os.path.join(path, "**", "*.txt"), recursive=True))

roots = []

# 1) transcripts/ folder
t_dir = os.path.join(ROOT, "transcripts")
if os.path.isdir(t_dir):
    roots.append(t_dir)

# 2) root-level @channel folders
for name in os.listdir(ROOT):
    if name.startswith("@"):
        p = os.path.join(ROOT, name)
        if os.path.isdir(p):
            roots.append(p)

print("=== Transcript roots detected ===")
total = 0
for r in sorted(set(roots)):
    c = count_txt(r)
    total += c
    print(f"{r} -> {c} .txt files")

print(f"\nTOTAL .txt files across all roots: {total}")
