import os
import requests
from openai import OpenAI

# --- Environment Variables ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WIX_API_KEY = os.getenv("WIX_API_KEY")
SITE_ID = "49c0ef6f-9ed8-42d5-aa44-dfd841c6f417"
COLLECTION_ID = "ForgedByFreedom_KB"

client = OpenAI(api_key=OPENAI_API_KEY)

headers = {
    "Authorization": WIX_API_KEY,
    "Content-Type": "application/json",
    "wix-site-id": SITE_ID,
}

# --- Functions ---
def push_to_wix(title, text):
    data = {
        "dataCollectionId": COLLECTION_ID,
        "dataItem": {"data": {"title": title, "text": text}},
    }
    r = requests.post(
        "https://www.wixapis.com/wix-data/v2/items",
        json=data,
        headers=headers,
    )
    if r.status_code == 200:
        print(f"✅ Uploaded to Wix: {title}")
    else:
        print(f"❌ Failed ({r.status_code}): {r.text}")

def main():
    print("🔍 Connecting to OpenAI and Wix...")
    files = client.files.list().data
    print(f"✅ Found {len(files)} OpenAI files.")

    for f in files:
        if not f.filename.startswith("master_transcript"):
            continue
        try:
            content = client.files.content(f.id).read().decode("utf-8", errors="ignore")
            push_to_wix(f.filename, content[:50000])  # upload safely in chunks
        except Exception as e:
            print(f"❌ Error on {f.filename}: {e}")

if __name__ == "__main__":
    main()

