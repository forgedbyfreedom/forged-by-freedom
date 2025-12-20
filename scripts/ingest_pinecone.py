import os
import requests
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRANSCRIPTS = os.path.join(ROOT, "transcripts_all")

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
EMBED_MODEL = "text-embedding-3-large"
HEADERS = {
    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
    "Content-Type": "application/json"
}

def embed(text):
    r = requests.post(
        EMBED_URL,
        headers=HEADERS,
        json={"model": EMBED_MODEL, "input": text}
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]

for channel in os.listdir(TRANSCRIPTS):
    ch_dir = os.path.join(TRANSCRIPTS, channel)
    if not os.path.isdir(ch_dir):
        continue

    for fname in os.listdir(ch_dir):
        if not fname.endswith(".txt"):
            continue

        path = os.path.join(ch_dir, fname)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()

        if len(text) < 200:
            continue

        vec = embed(text[:6000])

        index.upsert([{
            "id": f"{channel}:{fname}",
            "values": vec,
            "metadata": {
                "channel": channel,
                "episode": fname,
                "text": text[:1200]
            }
        }])

print("✅ Pinecone ingestion complete.")
