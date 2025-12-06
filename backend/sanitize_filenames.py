import os
import re
import unicodedata
import glob

def sanitize_filename(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-zA-Z0-9_\-.]", "_", name)
    return name

base_dirs = ["transcripts", "thinkbig", "backend"]

for base in base_dirs:
    for path in glob.glob(f"{base}/**/*.txt", recursive=True):
        folder, filename = os.path.split(path)
        safe = sanitize_filename(filename)
        if safe != filename:
            new_path = os.path.join(folder, safe)
            print(f"🧹 Renaming: {path} → {new_path}")
            os.rename(path, new_path)
print("✅ Filename cleanup complete.")
