import os, json, requests
from pathlib import Path
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "transcripts_all"

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

def embed(text):
    r = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
        json={"model": "text-embedding-3-large", "input": text},
        timeout=30
    )
    return r.json()["data"][0]["embedding"]

batch = []

for channel_dir in TRANSCRIPTS.iterdir():
    if not channel_dir.is_dir():
        continue

    for txt in channel_dir.glob("*.txt"):
        text = txt.read_text(errors="ignore")
        if len(text) < 200:
            continue

        vec = embed(text[:8000])

        batch.append({
            "id": f"{channel_dir.name}-{txt.stem}",
            "values": vec,
            "metadata": {
                "channel": channel_dir.name,
                "episode": txt.stem,
                "text": text[:2000],
                "source": f"{channel_dir.name} / {txt.name}"
            }
        })

        if len(batch) >= 50:
            index.upsert(batch)
            batch.clear()

if batch:
    index.upsert(batch)

print("✅ Pinecone ingestion complete")
