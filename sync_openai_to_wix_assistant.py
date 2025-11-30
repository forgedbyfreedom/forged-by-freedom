#!/usr/bin/env python3
"""
sync_openai_to_wix_assistant.py
---------------------------------
Syncs text transcripts stored in OpenAI File Storage (purpose=user_data or fine-tune)
to a Wix CMS Collection ("ForgedByFreedom_KB") using the Assistant API for retrieval.

Requirements:
  pip install openai requests python-dotenv
Environment variables:
  OPENAI_API_KEY
  WIX_API_KEY
  WIX_SITE_ID
"""

import os
import time
import requests
from openai import OpenAI


# ========================
# 🔧 Configuration
# ========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WIX_API_KEY = os.getenv("WIX_API_KEY")
WIX_SITE_ID = os.getenv("WIX_SITE_ID")

if not OPENAI_API_KEY:
    raise ValueError("❌ Missing OPENAI_API_KEY in environment.")
if not WIX_API_KEY:
    raise ValueError("❌ Missing WIX_API_KEY in environment.")
if not WIX_SITE_ID:
    raise ValueError("❌ Missing WIX_SITE_ID in environment.")

client = OpenAI(api_key=OPENAI_API_KEY)


# ========================
# ⚙️ Wix Upload Helper
# ========================

def push_to_wix(filename: str, content: str):
    """Uploads extracted content to Wix CMS."""
    url = "https://www.wixapis.com/wix-data/v2/items"
    headers = {
        "Authorization": WIX_API_KEY,
        "wix-site-id": WIX_SITE_ID,
        "Content-Type": "application/json"
    }
    data = {
        "collectionId": "ForgedByFreedom_KB",  # Your Wix collection name
        "item": {
            "title": filename,
            "body": content[:50000]  # Trim if over 50k chars
        }
    }

    print(f"⬆️ Uploading {filename} to Wix...")
    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        print(f"✅ Uploaded {filename} successfully.")
    else:
        print(f"⚠️ Wix upload failed ({response.status_code}): {response.text}")
        os.makedirs("failed_syncs", exist_ok=True)
        with open(f"failed_syncs/{filename}.txt", "w") as f:
            f.write(content)


# ========================
# 🚀 Sync Logic
# ========================

print("🔍 Listing OpenAI user_data and fine-tune files...")
files = [f for f in client.files.list().data if f.purpose in ["user_data", "fine-tune"]]
print(f"📁 Found {len(files)} file(s).")

if not files:
    print("❌ No eligible files found in OpenAI storage.")
    exit(1)

for f in files:
    print(f"\n⏳ Processing {f.filename} ({f.id})...")

    try:
        # 🧠 Create Assistant
        assistant = client.beta.assistants.create(
            name="Transcript Retriever",
            instructions=f"Return the full contents of the transcript file named {f.filename}.",
            model="gpt-4.1-mini",
            tools=[{"type": "retrieval"}]
        )

        # 📎 Attach file
        client.beta.assistants.files.create(
            assistant_id=assistant.id,
            file_id=f.id
        )

        # 🧵 Create a thread
        thread = client.beta.threads.create()

        # ▶️ Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions=f"Retrieve and print the contents of {f.filename}."
        )

        # ⏱ Wait for the assistant to finish
        while True:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run_status.status == "completed":
                break
            elif run_status.status == "failed":
                raise Exception("Assistant run failed.")
            time.sleep(2)

        # 💬 Fetch messages
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        if not messages.data or not messages.data[0].content:
            print(f"⚠️ No content retrieved from {f.filename}. Skipping.")
            continue

        content = messages.data[0].content[0].text.value.strip()

        if not content:
            print(f"⚠️ File {f.filename} returned empty content.")
            continue

        # 🚀 Upload to Wix
        push_to_wix(f.filename, content)

    except Exception as e:
        print(f"❌ Error syncing {f.filename}: {e}")

print("\n🎉 Done! All transcripts processed successfully.")

