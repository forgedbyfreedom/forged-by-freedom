#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ---------------- ENV ----------------
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

TRANSCRIPTS = Path(__file__).resolve().parents[1] / "transcripts"

summary = {}
total_words = 0
total_episodes = 0

for f in TRANSCRIPTS.rglob("*.txt"):
    channel = f.parent.name
    words = len(f.read_text(errors="ignore").split())

    summary.setdefault(channel, {"episodes": 0, "words": 0})
    summary[channel]["episodes"] += 1
    summary[channel]["words"] += words

    total_episodes += 1
    total_words += words

stats = {
    "total_channels": len(summary),
    "total_episodes": total_episodes,
    "total_words": total_words,
    "last_updated": datetime.now().isoformat()
}

(TRANSCRIPTS / "transcripts_summary.json").write_text(json.dumps(summary, indent=2))
(TRANSCRIPTS / "stats.json").write_text(json.dumps(stats, indent=2))

print("✅ Site stats regenerated")
