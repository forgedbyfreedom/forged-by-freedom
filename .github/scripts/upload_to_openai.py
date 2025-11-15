import os, glob, openai

key = os.getenv("OPENAI_API_KEY")
if not key:
    print("❌ No OPENAI_API_KEY found; skipping upload.")
    raise SystemExit(0)

openai.api_key = key

for path in glob.glob("**/master_transcript*.txt", recursive=True):
    print(f"📤 Uploading {path} ...")
    with open(path, "rb") as f:
        resp = openai.files.create(file=f, purpose="assistants")
        print(f"✅ Uploaded {path} → id={resp.id}")

