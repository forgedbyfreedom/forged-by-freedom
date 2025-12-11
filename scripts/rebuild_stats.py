#!/usr/bin/env python3
import os, json
from datetime import datetime

BASE_DIR = "transcripts"
summary = {}

for root, dirs, files in os.walk(BASE_DIR):
    channel = os.path.basename(root)
    txts = [f for f in files if f.endswith(".txt")]
    if txts:
        summary[channel] = {"episodes": len(txts), "words": 0}
        for f in txts:
            try:
                with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as fh:
                    summary[channel]["words"] += len(fh.read().split())
            except Exception:
                pass

stats = {
    "total_channels": len(summary),
    "total_episodes": sum(v["episodes"] for v in summary.values()),
    "total_words": sum(v["words"] for v in summary.values()),
    "last_updated": datetime.now().isoformat()
}

os.makedirs(BASE_DIR, exist_ok=True)
with open(os.path.join(BASE_DIR, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)
with open(os.path.join(BASE_DIR, "transcripts_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("✅ Rebuilt stats successfully:")
print(json.dumps(stats, indent=2))
