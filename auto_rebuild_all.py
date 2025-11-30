import os
import subprocess

BASE_DIR = "/Users/weero/thinkbig_podcast/transcripts"

print("\n=== 🚀 Starting multi-channel transcript rebuild ===")

for channel in os.listdir(BASE_DIR):
    channel_path = os.path.join(BASE_DIR, channel)

    # Only process subfolders that start with "@"
    if not os.path.isdir(channel_path) or not channel.startswith("@"):
        continue

    print(f"\n🔹 Processing channel: {channel}")

    # Run master transcript builder
    build_script = os.path.join(BASE_DIR, "build_master_transcripts.py")
    try:
        subprocess.run(["python", build_script], cwd=channel_path, check=True)
        print(f"✅ Rebuilt master transcript for {channel}")
    except subprocess.CalledProcessError:
        print(f"⚠️ Skipped {channel} — build script failed.")

    # Run GitHub uploader if available
    uploader_script = os.path.join(channel_path, "github_auto_push.sh")
    if os.path.exists(uploader_script):
        try:
            subprocess.run([uploader_script], check=True)
            print(f"✅ Uploaded {channel} transcripts to GitHub.")
        except subprocess.CalledProcessError:
            print(f"⚠️ GitHub push failed for {channel}")
    else:
        print(f"ℹ️ No uploader found for {channel}. Skipping push.")

print("\n=== ✅ All channels processed ===\n")

