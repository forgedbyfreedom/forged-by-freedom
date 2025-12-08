#!/usr/bin/env python3
"""
🚀 Forged By Freedom / ThinkBIG Full Automation Pipeline
- Downloads latest YouTube videos per channel
- Transcribes using Whisper
- Rebuilds master_transcript.txt
- Pushes updates to GitHub
"""

import os, subprocess, datetime, glob, time

# === CONFIG ===
ROOT = "/Users/weero/thinkbig_podcast"
YT_ROOT = os.path.join(ROOT, "downloads")
TRANSCRIPTS = os.path.join(ROOT, "transcripts")
PYTHON = os.path.join(ROOT, ".venv/bin/python3")
LOG_FILE = os.path.join(TRANSCRIPTS, "github_sync.log")

def log(msg):
    stamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{stamp} {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(f"{stamp} {msg}\n")

def find_git_root(start_path):
    cur = os.path.abspath(start_path)
    while cur != "/":
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        cur = os.path.dirname(cur)
    return None

GIT_ROOT = find_git_root(TRANSCRIPTS)
if not GIT_ROOT:
    log("❌ No .git repo found — aborting.")
    exit(1)

# === MAIN FUNCTIONS ===
def download_channel(channel_name):
    log(f"🎧 Checking for new videos from {channel_name}...")
    ch_path = os.path.join(YT_ROOT, channel_name)
    os.makedirs(ch_path, exist_ok=True)
    subprocess.run([
        "yt-dlp", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
        "-o", f"{ch_path}/%(title)s [%(id)s].%(ext)s",
        f"https://www.youtube.com/{channel_name}"
    ], check=False)

def transcribe_channel(channel_name):
    ch_path = os.path.join(YT_ROOT, channel_name)
    out_dir = os.path.join(TRANSCRIPTS, channel_name)
    os.makedirs(out_dir, exist_ok=True)
    audio_files = glob.glob(os.path.join(ch_path, "*.mp3"))
    if not audio_files:
        log(f"⚙️ No new audio found for {channel_name}.")
        return
    for audio in audio_files:
        base = os.path.splitext(os.path.basename(audio))[0]
        txt_path = os.path.join(out_dir, f"{base}.txt")
        if os.path.exists(txt_path):
            log(f"⏭️ Skipping {base} (already transcribed)")
            continue
        log(f"🗣️ Transcribing {base}...")
        subprocess.run([PYTHON, "-m", "whisper", audio, "--model", "small", "--output_dir", out_dir], check=False)
        os.remove(audio)
        log(f"✅ Finished {base}")

def rebuild_master_transcripts():
    log("🏗️ Rebuilding master transcripts...")
    subprocess.run([PYTHON, os.path.join(TRANSCRIPTS, "build_master_transcripts.py")], check=False)

def git_push():
    log("📤 Syncing updates to GitHub...")
    subprocess.run(["git", "-C", GIT_ROOT, "add", "-A"], check=False)
    subprocess.run(["git", "-C", GIT_ROOT, "commit", "-m", f"Auto update ({datetime.datetime.now():%Y-%m-%d %H:%M:%S})"], check=False)
    subprocess.run(["git", "-C", GIT_ROOT, "push", "origin", "main"], check=False)

# === EXECUTION ===
log("=== 🚀 Starting Full ThinkBIG Podcast Automation ===")
channels = [d for d in os.listdir(TRANSCRIPTS) if d.startswith("@")]
for ch in channels:
    start = time.time()
    log(f"\n🔹 Processing {ch}")
    try:
        download_channel(ch)
        transcribe_channel(ch)
        rebuild_master_transcripts()
        log(f"✅ {ch} processed in {round(time.time() - start, 1)}s")
    except Exception as e:
        log(f"❌ Error on {ch}: {e}")

git_push()
log("=== ✅ All channels updated & pushed ===")
