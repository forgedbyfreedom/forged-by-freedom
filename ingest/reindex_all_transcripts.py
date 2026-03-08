#!/usr/bin/env python3
import os, time, hashlib, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from pinecone import Pinecone

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_HOST = os.environ["PINECONE_HOST"]

INDEX_NAME = "forged-freedom-ai"
EMBED_MODEL = "text-embedding-3-large"
TRANSCRIPTS_DIR = Path("transcripts")

BATCH = 16
SLEEP = 1.5

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

def embed(texts):
    r = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120
    )
    data = r.json()
    return [d["embedding"] for d in data["data"]]

def stable_id(text):
    return hashlib.sha1(text.encode("utf-8","ignore")).hexdigest()

def namespace_for_channel(channel):
    if "thinkbig" in channel.lower():
        return "thinkbig_priority"
    if "anabolic" in channel.lower():
        return "anabolic_bodybuilding_priority"
    return "default"

def chunk(text, max_chars=900):
    out, buf = [], ""
    for s in text.split("."):
        if len(buf) + len(s) > max_chars:
            out.append(buf.strip())
            buf = ""
        buf += s + ". "
    if buf.strip():
        out.append(buf.strip())
    return out

def main():
    total = 0
    for channel_dir in TRANSCRIPTS_DIR.iterdir():
        if not channel_dir.is_dir():
            continue

        namespace = namespace_for_channel(channel_dir.name)

        for f in channel_dir.glob("*.txt"):
            raw = f.read_text(errors="ignore")
            chunks = chunk(raw)

            for i in range(0, len(chunks), BATCH):
                batch = chunks[i:i+BATCH]
                try:
                    vecs = embed(batch)
                except Exception:
                    continue

                payload = []
                for t, v in zip(batch, vecs):
                    payload.append({
                        "id": stable_id(t),
                        "values": v,
                        "metadata": {
                            "channel": channel_dir.name,
                            "source": f.name,
                            "text": t
                        }
                    })

                index.upsert(vectors=payload, namespace=namespace)
                total += len(payload)
                time.sleep(SLEEP)

    print(f"\n🔥 REINDEX COMPLETE — {total} vectors")

if __name__ == "__main__":
    main()
