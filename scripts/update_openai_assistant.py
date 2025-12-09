#!/usr/bin/env python3
import os, json
from openai import OpenAI

key = os.getenv("OPENAI_API_KEY")
asst_id = os.getenv("OPENAI_ASSISTANT_ID")

if not key or not asst_id:
    print("⚠️ Missing OpenAI credentials or Assistant ID.")
    raise SystemExit(0)

client = OpenAI(api_key=key)
index_path = "transcripts/file_index.json"

if not os.path.exists(index_path):
    print("⚠️ file_index.json not found — skipping assistant update.")
    raise SystemExit(0)

with open(index_path, "r") as f:
    file_index = json.load(f)

new_file_ids = [f.get("file_id") for f in file_index if f.get("file_id")]
print(f"🔗 Linking {len(new_file_ids)} files to assistant {asst_id}...")

try:
    client.beta.assistants.update(asst_id, file_ids=new_file_ids)
    print("✅ Assistant successfully updated.")
except Exception as e:
    print(f"⚠️ Error updating assistant: {e}")
