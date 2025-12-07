#!/usr/bin/env python3
import os
import subprocess
import datetime
import glob

# === CONFIG ===
TRANSCRIPTS_ROOT = "/Users/weero/thinkbig_podcast/transcripts"

print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] === 🚀 Uploading Master Transcripts to GitHub ===")

# Step 1 — Find all master transcript files (any channel)
master_files = glob.glob(os.path.join(TRANSCRIPTS_ROOT, "@*", "master_transcript*.txt"))

if not master_files:
    print("⚠️ No master transcripts found.")
    exit(0)

# Step 2 — Stage only master transcript files
try:
    subprocess.run(
        ["git", "-C", TRANSCRIPTS_ROOT, "add"] + master_files,
        check=True
    )
except subprocess.CalledProcessError:
    print("⚠️ Git add failed — make sure you’re inside the correct repo.")
    exit(1)

# Step 3 — Commit and push
try:
    commit_message = f"Auto-upload master transcripts ({datetime.datetime.now():%Y-%m-%d %H:%M:%S})"
    result = subprocess.run(
        ["git", "-C", TRANSCRIPTS_ROOT, "commit", "-m", commit_message],
        capture_output=True,
        text=True
    )

    # Only push if there were actual changes
    if "nothing to commit" in result.stdout:
        print("ℹ️ No new or updated master transcripts — skipping push.")
    else:
        subprocess.run(["git", "-C", TRANSCRIPTS_ROOT, "push", "origin", "main"], check=True)
        print("✅ All new master transcripts uploaded to GitHub successfully!")
except subprocess.CalledProcessError:
    print("⚠️ Git push failed — check your connection or repo access.")
#!/usr/bin/env python3
import os
import subprocess
import datetime
import glob

# === CONFIG ===
TRANSCRIPTS_ROOT = "/Users/weero/thinkbig_podcast/transcripts"

print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] === 🚀 Uploading Master Transcripts to GitHub ===")

# Step 1 — Find all master transcript files (any channel)
master_files = glob.glob(os.path.join(TRANSCRIPTS_ROOT, "@*", "master_transcript*.txt"))

if not master_files:
    print("⚠️ No master transcripts found.")
    exit(0)

# Step 2 — Stage all master transcripts
try:
    subprocess.run(["git", "-C", TRANSCRIPTS_ROOT, "add", "*/master_transcript*.txt"], check=True)
except subprocess.CalledProcessError:
    print("⚠️ Git add failed — make sure you’re inside the correct repo.")
    exit(1)

# Step 3 — Commit and push
try:
    commit_message = f"Auto-upload master transcripts ({datetime.datetime.now():%Y-%m-%d %H:%M:%S})"
    subprocess.run(["git", "-C", TRANSCRIPTS_ROOT, "commit", "-m", commit_message], check=False)
    subprocess.run(["git", "-C", TRANSCRIPTS_ROOT, "push", "origin", "main"], check=True)
    print("✅ All master transcript versions uploaded to GitHub successfully!")
except subprocess.CalledProcessError:
    print("⚠️ Git push failed — check your connection or repo access.")

