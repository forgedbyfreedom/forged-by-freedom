import os
from openai import OpenAI

# Initialize client using your environment key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LOCAL_FILES = [
    "transcripts/master_transcript_combined.txt"
]

uploaded_count = 0
for file_path in LOCAL_FILES:
    if not os.path.exists(file_path):
        print(f"⚠️ Skipping {file_path}: not found.")
        continue
    with open(file_path, "rb") as f:
        print(f"⏫ Uploading {file_path}...")
        uploaded = client.files.create(file=f, purpose="user_data")
        print(f"✅ Uploaded {file_path} as {uploaded.id}")
        uploaded_count += 1

print(f"\n🎉 Done! Uploaded {uploaded_count} file(s) successfully.")

