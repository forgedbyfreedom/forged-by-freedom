import os
import uuid
from pinecone import Pinecone
from openai import OpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("PINECONE_HOST")
INDEX_NAME = "forged-freedom-ai"

assert OPENROUTER_API_KEY, "OPENROUTER_API_KEY missing"
assert PINECONE_API_KEY, "PINECONE_API_KEY missing"
assert PINECONE_HOST, "PINECONE_HOST missing"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

TRANSCRIPTS_ROOT = "transcripts"

def embed(text):
    resp = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return resp.data[0].embedding

for channel in os.listdir(TRANSCRIPTS_ROOT):
    channel_path = os.path.join(TRANSCRIPTS_ROOT, channel)
    if not os.path.isdir(channel_path):
        continue

    for fname in os.listdir(channel_path):
        if not fname.endswith(".txt"):
            continue

        path = os.path.join(channel_path, fname)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        if len(text) < 500:
            continue

        vector = embed(text)

        metadata = {
            "channel": channel,
            "file": fname,
            "source": "YouTube",
            "show": channel.replace("@", ""),
            "type": "transcript",
            "text": text[:2000]
        }

        index.upsert([
            (str(uuid.uuid4()), vector, metadata)
        ])

print("✅ Pinecone ingest complete")
