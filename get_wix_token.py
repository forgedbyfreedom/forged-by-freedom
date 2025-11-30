import requests

# 🧩 Replace these with your real credentials from the Headless App
CLIENT_ID = "aaf0c7c2-5b7a-485a-917a-5da4800379b3"
CLIENT_SECRET = "PASTE_YOUR_LONG_SECRET_HERE"

# ✅ Correct OAuth token endpoint for Wix Headless
url = "https://www.wixapis.com/oauth2/token"

# Wix requires grant_type and client credentials as form fields
data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

response = requests.post(url, data=data, headers=headers)

print("\n🔑 Status:", response.status_code)
print("📦 Response:\n", response.text)

