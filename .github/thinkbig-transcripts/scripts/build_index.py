import os, json, hashlib, time
from datetime import datetime

ROOT_DIR = os.getcwd()
index = []
hash_set = set()

print("🧹 Scanning for transcripts...")

for root, dirs, files in os.walk(ROOT_DIR):
    for file in files:
        if file.endswith(".txt"):
            path = os.path.join(root, file)
            with open(path, "rb") as f:
                data = f.read()
            file_hash = hashlib.md5(data).hexdigest()

            if file_hash in hash_set:
                print(f"⚠️ Duplicate found, skipping: {path}")
                continue

            hash_set.add(file_hash)
            tokens = len(data.decode(errors="ignore").
            channel = os.path.basename(os.path.dirname(path))

            index.append({
                "channel": channel,
                "filename": file,
                "path": path.replace(ROOT_DIR, ""),
                "tokens": tokens,
                "hash": file_hash,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            })

print(f"✅ Indexed {len(index)} unique transcripts.")

with open("file_index.json", "w") as f:
    json.dump(index, f, indent=2)

print("💾 file_index.json written successfully.")
