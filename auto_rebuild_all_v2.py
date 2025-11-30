#!/usr/bin/env python3
import os
import subprocess
import time
import datetime

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
CHANNELS = [
    d for d in os.listdir(TRANSCRIPTS)
    if d.startswith("@") and os.path.isdir(os.path.join(TRANSCRIPTS, d))
]
LOG_FILE = os.path.join(TRANSCRIPTS, "github_sync.log")

def log(message: str):
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
        repo_root = os.path.dirname(os.path.abspath(__file__))
        build_script = os.path.join(repo_root, "build_master_transcripts.py")
        subprocess.run(["python", build_script], check=True)

        runtime = round(time.time() - start, 1)
        log(f"✅ Rebuilt master transcript for {ch} in {runtime}s")

        # Push to GitHub
        subprocess.run(["git", "-C", ROOT, "add", "-A"], check=True)
        subprocess.run([
            "git", "-C", ROOT, "commit", "-m",
            f"Auto update: {ch} ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        ], check=False)
        subprocess.run(["git", "-C", ROOT, "push"], check=True)
        log(f"✅ Synced {ch} to GitHub")

    except subprocess.CalledProcessError as e:
        log(f"❌ Error processing {ch}: {e}")
        continue
    except Exception as e:
        log(f"❌ Unexpected error for {ch}: {e}")
        continue

log("=== ✅ Auto Rebuild Complete ===")
