#!/usr/bin/env python3
"""
Collect ALL transcripts across repo into transcripts_all/
Authoritative source for stats, search, and Pinecone
"""

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "transcripts_all"
DEST.mkdir(exist_ok=True)

EXCLUDE_DIRS = {
    ".git", ".venv", "node_modules", "large_media_backup",
    "large_media_split", "__pycache__"
}

def is_excluded(path: Path):
    return any(p in EXCLUDE_DIRS for p in path.parts)

copied = 0
seen = set()

for path in ROOT.rglob("*.txt"):
    if is_excluded(path):
        continue

    # channel name = parent folder or @channel
    channel = path.parent.name.replace("@", "").strip()
    filename = path.name

    target_dir = DEST / channel
    target_dir.mkdir(exist_ok=True)

    target = target_dir / filename

    key = (channel, filename)
    if key in seen:
        continue

    shutil.copy2(path, target)
    seen.add(key)
    copied += 1

print(f"✅ Collected {copied} transcripts into {DEST}")
