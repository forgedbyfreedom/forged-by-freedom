#!/usr/bin/env python3
"""
Collect ALL transcript .txt files into transcripts_all/
This is the single authoritative aggregation step.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "transcripts_all"
DEST.mkdir(exist_ok=True)

EXCLUDE_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", 
    "large_media_backup", "large_media_split"
}

def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)

copied = 0
seen = set()

for txt in ROOT.rglob("*.txt"):
    if is_excluded(txt):
        continue

    channel = txt.parent.name.replace("@", "").strip()
    target_dir = DEST / channel
    target_dir.mkdir(exist_ok=True)

    key = (channel, txt.name)
    if key in seen:
        continue

    shutil.copy2(txt, target_dir / txt.name)
    seen.add(key)
    copied += 1

print(f"✅ Collected {copied} transcripts into {DEST}")
