#!/usr/bin/env python3
import os, subprocess, time, datetime

# === Auto-detect project root (the folder containing .git) ===
def find_git_root(start_path="."):
    cur = os.path.abspath(start_path)
    while cur != "/":
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        cur = os.path.dirname(cur)
    return None

ROOT = find_git_root(os.getcwd())
if not ROOT:
    print("❌ No .git repo found — aborting.")
    exit(1)

TRANSCRIPTS = ROOT
CHANNELS = [d for d in os.listdir(TRANSCRIPTS) if d.startswith("@") and os.path.isdir(os.path.join(TRANSCRIPTS, d))]
LOG_FILE = os.path.join(TRANSCRIPTS, "github_sync.log")

def log(message):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} {message}\n")
    print(message)

log(f"=== 🚀 Auto Rebuild Started ({len(CHANNELS)} channels) ===")

for ch in CHANNELS:
    ch_path = os.path.join(TRANSCRIPTS, ch)
    start = time.time()
    log(f"\n🔹 Processing channel: {ch}")
    try:
        subprocess.run(["python3", os.path.join(TRANSCRIPTS, "build_master_transcripts.py")], check=True)
        runtime = round(time.time() - start, 1)
        log(f"✅ Rebuilt master transcript for {ch} in {runtime}s")

        # Push to GitHub
        subprocess.run(["git", "-C", ROOT, "add", "-A"], check=True)
        subprocess.run(["git", "-C", ROOT, "commit", "-m", f"Auto update: {ch} ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"], check=False)
        subprocess.run(["git", "-C", ROOT, "push"], check=True)
        log(f"✅ Synced {ch} to GitHub")

    except subprocess.CalledProcessError as e:
        log(f"❌ Error processing {ch}: {e}")
        continue

log("=== ✅ All channels processed successfully ===")

