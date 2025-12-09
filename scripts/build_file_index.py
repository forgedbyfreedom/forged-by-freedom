#!/usr/bin/env python3
import os
import json
from datetime import datetime

ROOT_DIR = "transcripts"
OUTPUT_FILE = os.path.join(ROOT_DIR, "file_index.json")
SUMMARY_FILE = os.path.join(ROOT_DIR, "transcripts_summary.json")
STATS_FILE = os.path.join(ROOT_DIR, "stats.json")

def get_transcripts(root):
    files = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".txt"):
                files.append(os.path.join(dirpath, f))
    return files

def summarize_files(files):
    summary = {}
    for f in files:
        channel = os.path.basename(os.path.dirname(f))
        with open(f, "r", encoding="utf-8", errors="ignore") as fp:
            text = fp.read()
        words = len(text.split())
        summary.setdefault(channel, {"episodes": 0, "words": 0})
        summary[channel]["episodes"] += 1
        summary[channel]["words"] += words
    return summary

def main():
    os.makedirs(ROOT_DIR, exist_ok=True)
    transcripts = get_transcripts(ROOT_DIR)
    print(f"📚 Found {len(transcripts)} transcripts.")

    index_data = []
    for f in transcripts:
        rel_path = os.path.relpath(f, ROOT_DIR)
        index_data.append({
            "path": rel_path,
            "size": os.path.getsize(f),
            "modified": datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        })

    summary = summarize_files(transcripts)
    totals = {
        "total_channels": len(summary),
        "total_episodes": sum(s["episodes"] for s in summary.values()),
        "total_words": sum(s["words"] for s in summary.values()),
        "last_updated": datetime.now().isoformat()
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(totals, f, indent=2)

    print(f"✅ Updated: {OUTPUT_FILE}, {SUMMARY_FILE}, {STATS_FILE}")
    print(f"📊 {totals}")

if __name__ == "__main__":
    main()
