import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEST = os.path.join(ROOT, "transcripts_all")

os.makedirs(DEST, exist_ok=True)

FOUND = 0

for root, dirs, files in os.walk(ROOT):
    # skip junk
    if any(skip in root for skip in [
        ".git", "node_modules", ".venv", "backend", "dist", "__pycache__"
    ]):
        continue

    for f in files:
        if f.lower().endswith(".txt"):
            src = os.path.join(root, f)

            # channel name = parent folder
            channel = os.path.basename(os.path.dirname(src))
            channel_dir = os.path.join(DEST, channel)

            os.makedirs(channel_dir, exist_ok=True)

            dst = os.path.join(channel_dir, f)

            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                FOUND += 1

print(f"✅ Collected {FOUND} transcripts into transcripts_all/")
