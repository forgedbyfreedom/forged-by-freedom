#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ---------------- ENV ----------------
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

ROOT = Path(__file__).resolve().parents[1] / "transcripts"

files = []
summary = {}

for f in ROOT.rglob("*.txt"):
    channel = f.parent.name
    text = f.read_text(errors="ignore")
    words = len(text.split())

    summary.setdefault(channel, {"episodes": 0, "words": 0})
    summary[channel]["episodes"] += 1
    summary[channel]["words"] += words

    files.append({
        "path": str(f.relative_to(ROOT)),
        "size": f.stat().st_size,
        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
    })

stats = {
    "total_channels": len(summary),
    "total_episodes": sum(v["episodes"] for v in summary.values()),
    "total_words": sum(v["words"] for v in summary.values()),
    "last_updated": datetime.now().isoformat()
}

(ROOT / "file_index.json").write_text(json.dumps(files, indent=2))
(ROOT / "transcripts_summary.json").write_text(json.dumps(summary, indent=2))
(ROOT / "stats.json").write_text(json.dumps(stats, indent=2))

print("✅ File index + stats updated")
