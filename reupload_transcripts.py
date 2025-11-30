from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Reupload one or more transcripts with correct purpose
for filename in ["master_transcript_combined.txt", "fetch_summary.txt"]:
    if not os.path.exists(filename):
        print(f"⚠️ Skipping {filename}: file not found locally.")
        continue
    with open(filename, "rb") as f:
        uploaded = client.files.create(file=f, purpose="fine-tune")
        print(f"✅ Reuploaded {filename}: {uploaded.id}")
from openai import OpenAI
import os, time

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("🔄 Starting reupload of restricted transcripts...")

files = client.files.list().data
reuploaded = 0

for f in files[:50]:  # test first 50 before full batch
    if f.purpose == "assistants":
        try:
            # Download file content via the 'content' endpoint
            print(f"⏬ Attempting to copy {f.filename} ({f.id})...")
            content = client.files.content(f.id).read()

            # Write temporarily
            temp_path = f.filename.replace(".txt", "_copy.txt")
            with open(temp_path, "wb") as temp_file:
                temp_file.write(content)

            # Reupload with fine-tune purpose
            with open(temp_path, "rb") as temp_file:
                uploaded = client.files.create(
                    file=temp_file,
                    purpose="fine-tune"
                )
            reuploaded += 1
            print(f"✅ Reuploaded as {uploaded.id}")

            os.remove(temp_path)
            time.sleep(1)
        except Exception as e:
            print(f"❌ Skipped {f.filename}: {e}")

print(f"\n🎉 Done! Reuploaded {reuploaded} files successfully.")
