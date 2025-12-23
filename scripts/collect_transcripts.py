#!/usr/bin/env python3
"""
Collect ALL transcripts across repo into transcripts_all/
Authoritative source for stats, search, and Pinecone
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "transcripts_all"
DEST.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__",
    "backend", "dist", "build",
    "large_media_backup", "large_media_split",
}

def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)

copied = 0
seen = set()

for path in ROOT.rglob("*.txt"):
    if is_excluded(path):
        continue

    channel = path.parent.name.replace("@", "").strip() or "unknown"
    filename = path.name

    target_dir = DEST / channel
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / filename
    key = (channel, filename)

    if key in seen:
        continue

    if not target.exists():
        shutil.copy2(path, target)
        copied += 1

    seen.add(key)

print(f"✅ Collected {copied} transcripts into {DEST}")
