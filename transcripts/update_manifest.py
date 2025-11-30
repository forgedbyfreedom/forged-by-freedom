#!/usr/bin/env python3
import os, json, datetime

# Base directory for your transcripts repo
base_dir = "./"

# Gather all snapshot and transcript files
snapshots = sorted([f for f in os.listdir(base_dir) if f.startswith("snapshot_") and f.endswith(".json")])
masters = sorted([f for f in os.listdir(base_dir) if f.startswith("master_transcript") and f.endswith(".txt")])
episodes = sorted([
    f for f in os.listdir(base_dir)
    if f.endswith(".txt") and not f.startswith("master_transcript")
])
latest = "latest.json" if os.path.exists(os.path.join(base_dir, "latest.json")) else None

# Build manifest dictionary
manifest = {
    "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "snapshots": snapshots,
    "latest_snapshot": snapshots[-1] if snapshots else None,
    "master_transcripts": masters,
    "episode_files": episodes,
    "latest_json": latest,
    "total_files": len(snapshots) + len(masters) + len(episodes) + (1 if latest else 0)
}

# Save manifest.json
with open(os.path.join(base_dir, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

print(f"✅ Manifest updated: {manifest['total_files']} files total")
if manifest["latest_snapshot"]:
    print(f"🕓 Latest snapshot: {manifest['latest_snapshot']}")
if manifest["master_transcripts"]:
    print(f"📘 Master transcripts: {', '.join(masters)}")

