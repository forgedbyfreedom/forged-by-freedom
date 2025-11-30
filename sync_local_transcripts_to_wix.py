#!/usr/bin/env python3
"""
🚀 Sync Local Transcripts to Wix CMS

This script uploads all `.txt` files from your local transcripts folder
to your Wix CMS collection called "transcripts".

Requirements:
  pip install requests

Environment (must be set before running):
  export WIX_API_KEY="IST.eyJraWQiOiJQb3pIX2FDMiIsImFsZyI6IlJTMjU2In0.eyJkYXRhIjoie1wiaWRcIjpcIjY2ZWNmM2Y3LWY4OTUtNGM3OS04MDdhLWM4NWI0NDEzMDY5NlwiLFwiaWRlbnRpdHlcIjp7XCJ0eXBlXCI6XCJhcHBsaWNhdGlvblwiLFwiaWRcIjpcIjk0M2ZlNjg0LWEyYzUtNDI3Yy05ZWVkLWIxODAxZmE0N2NhMFwifSxcInRlbmFudFwiOntcInR5cGVcIjpcImFjY291bnRcIixcImlkXCI6XCJlZDc1ODYyZC00Y2JjLTQ3NmEtYjhjYy00ZTk0NzViMjg5MTBcIn19IiwiaWF0IjoxNzY0Mzg0MjYxfQ.mgN_ak5tDbRdLdlbJ-Mi0GEDkxTwKDnYeKUnzYx7jlqwBCJi2v-PKPNXfeHGSELfMQNYLqK2Wj3_PW1MqeQnOu04Dw5UX7dI9VkmYCKXQG72dhJuTqZ5mJsvqRIqEaE0n-I12cBOrApXE6Pz0WXD2W-5o4L8kQrNP3shgnhpCKbxjrnOL-sO5mX1yr7URpqR9QPZVSZwXdIwAB33tm-ynayYbKKh8aGgA-Xc3FBNuafbVUvFsjhWfJ8HjCb3zWqnMSbixBL4anhWBJOd0S6qgs5JfX2YVNl_S2SBIe9eOLR8rwW4JqmDXlNQHjEvjsc_LCrp1x7Qs5beLtWLP2RhPQ"
  export WIX_SITE_ID="49c0ef6f-9ed8-42d5-aa44-dfd841c6f417"
"""

import os
import json
import requests
from time import sleep

# ============================================
# 🔧 CONFIGURATION
# ============================================
WIX_API_KEY = os.getenv("WIX_API_KEY")
WIX_SITE_ID = os.getenv("WIX_SITE_ID")

# ✅ This must match your Wix CMS collection name EXACTLY
WIX_COLLECTION_ID = "transcripts"

if not WIX_API_KEY:
    raise ValueError("❌ Missing WIX_API_KEY. Please export it before running.")
if not WIX_SITE_ID:
    raise ValueError("❌ Missing WIX_SITE_ID. Please export it before running.")
if not isinstance(WIX_COLLECTION_ID, str) or not WIX_COLLECTION_ID.strip():
    raise ValueError("❌ WIX_COLLECTION_ID must be a valid string (check your collection name).")

# ============================================
# 📂 LOCAL SETTINGS
# ============================================
TRANSCRIPTS_DIR = os.path.expanduser("~/forged-by-freedom-st/transcripts")
HEADERS = {
    "Authorization": WIX_API_KEY,
    "Content-Type": "application/json"
}

# ============================================
# 🔍 FETCH EXISTING ITEMS
# ============================================
def fetch_existing_titles():
    print("🔍 Fetching existing titles from Wix...")
    url = "https://www.wixapis.com/wix-data/v2/items/query"
    payload = {
        "dataCollectionId": WIX_COLLECTION_ID,
        "query": {}
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code != 200:
            print(f"⚠️ Failed to fetch titles ({response.status_code}): {response.text}")
            return []
        data = response.json()
        items = data.get("items", [])
        titles = [item.get("title", "").strip().lower() for item in items if "title" in item]
        print(f"✅ Found {len(titles)} existing items on Wix.")
        return titles
    except Exception as e:
        print(f"⚠️ Error fetching titles: {e}")
        return []

# ============================================
# ⬆️ UPLOAD FILE TO WIX
# ============================================
def upload_transcript(title, content):
    url = "https://www.wixapis.com/wix-data/v2/items"
    payload = {
        "dataCollectionId": WIX_COLLECTION_ID,
        "item": {
            "title": title,
            "content": content
        }
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"✅ Uploaded: {title}")
        else:
            print(f"⚠️ Upload failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Error uploading '{title}': {e}")

# ============================================
# 🚀 MAIN SYNC LOGIC
# ============================================
def main():
    print(f"📂 Scanning folder: {TRANSCRIPTS_DIR}")
    if not os.path.isdir(TRANSCRIPTS_DIR):
        raise FileNotFoundError(f"❌ Directory not found: {TRANSCRIPTS_DIR}")

    existing_titles = fetch_existing_titles()

    files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith(".txt")]
    print(f"🧾 Found {len(files)} local .txt files.\n")

    uploaded, skipped = 0, 0

    for filename in files:
        title = os.path.splitext(filename)[0].strip()
        if title.lower() in existing_titles:
            print(f"⏭️ Skipped duplicate: {title}")
            skipped += 1
            continue

        with open(os.path.join(TRANSCRIPTS_DIR, filename), "r", encoding="utf-8") as f:
            content = f.read()

        upload_transcript(title, content)
        uploaded += 1
        sleep(0.5)  # polite rate limiting

    print(f"\n🎉 Done! Uploaded {uploaded} new file(s), skipped {skipped} duplicate(s).")

# ============================================
# 🏁 RUN
# ============================================
if __name__ == "__main__":
    main()

