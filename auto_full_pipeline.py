#!/usr/bin/env python3
import os, subprocess, time, datetime, glob, shutil

# === CONFIG ===
YT_ROOT = "/Users/weero/thinkbig_podcast/downloads"
AUDIO_TMP = "/Users/weero/thinkbig_podcast/audio_tmp"
TRANSCRIPTS = "/Users/weero/thinkbig_podcast/transcripts"
PYTHON = "/Users/weero/thinkbig_podcast/.venv/bin/python3"
CHANNELS = [d for d in os.listdir(TRANSCRIPTS) if d.startswith("@")]
LOG_FILE = os.path.join(TRANSCRIPTS, "github_sync.log")

# === UTILITIES ===
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

# === STEP 1: DOWNLOAD NEW VIDEOS ===
def download_channel(channel_name, playlist_url=None):
    channel_path = os.path.join(YT_ROOT, channel_name)
    os.makedirs(channel_path, exist_ok=True)
    log(f"🎧 Checking for new videos from {channel_name}...")

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", f"{channel_path}/%(title)s [%(id)s].%(ext)s",
        f"https://www.youtube.com/{channel_name}",
    ]
    subprocess.run(cmd, check=False)

# === STEP 2: TRANSCRIBE AUDIO FILES ===
def transcribe_audio(channel_name):
    ch_tmp = os.path.join(AUDIO_TMP, channel_name)
    ch_out = os.path.join(TRANSCRIPTS, channel_name)
    os.makedirs(ch_out, exist_ok=True)

    audio_files = glob.glob(os.path.join(YT_ROOT, channel_name, "*.mp3"))
    if not audio_files:
        log(f"⚙️ No new audio found for {channel_name}.")
        return

    for audio in audio_files:
        base = os.path.splitext(os.path.basename(audio))[0]
        txt_path = os.path.join(ch_out, f"{base}.txt")

        if os.path.exists(txt_path):
            log(f"⏭️ Skipping existing {base}")
            continue

        log(f"🗣️ Transcribing {base} ...")
        subprocess.run([PYTHON, "-m", "whisper", audio, "--model", "small", "--output_dir", ch_out], check=False)
        os.remove(audio)
        log(f"✅ Transcribed and removed audio: {base}")

# === STEP 3: REBUILD MASTER TRANSCRIPTS ===
def rebuild_master_transcripts():
    log("📚 Rebuilding all master transcripts...")
    subprocess.run([PYTHON, os.path.join(TRANSCRIPTS, "build_master_transcripts.py")], check=False)

# === STEP 4: GIT PUSH ===
def git_push():
    log("📤 Syncing to GitHub...")
    subprocess.run(["git", "-C", GIT_ROOT, "add", "-A"], check=False)
    subprocess.run(["git", "-C", GIT_ROOT, "commit", "-m", f"Auto update: {datetime.datetime.now()}"], check=False)
    subprocess.run(["git", "-C", GIT_ROOT, "push"], check=False)

# === MAIN PIPELINE ===
log("=== 🚀 Starting Full ThinkBig Podcast Automation ===")
for ch in CHANNELS:
    start = time.time()
    log(f"\n🔹 Processing channel: {ch}")
    try:
        download_channel(ch)
        transcribe_audio(ch)
        rebuild_master_transcripts()
        runtime = round(time.time() - start, 1)
        log(f"✅ {ch} processed successfully in {runtime}s")
    except Exception as e:
        log(f"❌ Error on {ch}: {e}")
        continue

git_push()
log("=== ✅ All channels updated & pushed ===")

#!/usr/bin/env python3
import os
import subprocess
import datetime
import glob
import shutil

# === CONFIG ===
TRANSCRIPTS_ROOT = "/Users/weero/thinkbig_podcast/transcripts"
DOWNLOADS_ROOT = "/Users/weero/thinkbig_podcast/downloads"
CHANNELS = [
    "@FoundMyFitness",
    "@bodybuildingcom",
    "@theconditioncoaches",
    "@RenaissancePeriodization",
    "@ChrisBumstead",
    "@PeterAttiaMD",
    "@eliteftsofficial",
    "@hanyrambod_FST7",
    "@HighLifeWorkout",
    "@sam_sulek",
    "@BarbellMedicine",
    "@RyanHumiston",
    "@anabolicuniversity",
    "@rxmuscle",
    "@ThinkBIGBodybuilding",
    "@NasmOrgPersonalTrainer",
    "@ISSAPersonalTrainer",
    "@NicksStrengthandPower",
    "@MulliganBrothers",
    "@DrGabrielleLyon",
    "@anabolicbodybuilding",
    "@JeffNippard",
    "@realtattered",
]
ARCHIVE_FOLDER = os.path.join(TRANSCRIPTS_ROOT, "master_archive")

# === START ===
print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] === 🚀 Starting Full ThinkBig Podcast Automation ===")

os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

for channel in CHANNELS:
    channel_dir = os.path.join(TRANSCRIPTS_ROOT, channel)
    print(f"\n🔹 Processing channel: {channel}")
    os.makedirs(channel_dir, exist_ok=True)

    # Step 1: Download latest audio
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 🎧 Checking for new videos from {channel}...")
    try:
        subprocess.run([
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "-o", f"{DOWNLOADS_ROOT}/{channel}/%(title)s [%(id)s].%(ext)s",
            f"https://www.youtube.com/{channel}"
        ], check=True)
    except subprocess.CalledProcessError:
        print(f"⚠️  Download failed for {channel}. Continuing...")
        continue

    # Step 2: Run Whisper or transcription tool (placeholder)
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 🧠 Transcribing audio for {channel}...")
    # Normally you'd call your transcription script here
    # Example: subprocess.run(["python", "transcribe_audio.py", channel_dir])

    # Step 3: Build master transcript
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 🏗️ Rebuilding master transcript for {channel}...")
    try:
        subprocess.run(["python", os.path.join(TRANSCRIPTS_ROOT, "build_master_transcripts.py")], check=True)
        print(f"✅ Master transcript built for {channel}")
    except subprocess.CalledProcessError:
        print(f"⚠️  Failed to rebuild master transcript for {channel}")
        continue

    # Step 4: Copy all master transcripts to archive
    master_files = glob.glob(os.path.join(channel_dir, "master_transcript*.txt"))
    for f in master_files:
        shutil.copy2(f, os.path.join(ARCHIVE_FOLDER, f"{channel}_{os.path.basename(f)}"))

    # Step 5: Commit & push per-channel
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 🌀 Syncing {channel} to GitHub...")
    try:
        subprocess.run(["git", "add", f"{channel}/master_transcript*.txt"], check=True)
        subprocess.run([
            "git", "commit",
            "-m", f"Auto update: {channel} ({datetime.datetime.now():%Y-%m-%d %H:%M:%S})"
        ], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"✅ Synced {channel} to GitHub.")
    except subprocess.CalledProcessError:
        print(f"⚠️  Git push skipped or no changes for {channel}.")

# === FINAL STEP ===
print("\n[{}] 🚀 Uploading all master_transcript versions to GitHub...".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
try:
    subprocess.run(["git", "add", "*/master_transcript*.txt"], check=True)
    subprocess.run(["git", "add", "master_archive/*.txt"], check=True)
    subprocess.run([
        "git", "commit",
        "-m", f"Auto upload all master transcripts ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
    ], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    print("[✅] All master transcript versions successfully pushed to GitHub.")
except subprocess.CalledProcessError:
    print("[⚠️] No new master transcripts to push or git push failed.")

print("\n=== ✅ All channels processed successfully ===")

