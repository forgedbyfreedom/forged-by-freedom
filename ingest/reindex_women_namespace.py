#!/usr/bin/env python3
import os, re, uuid, time
from pathlib import Path
from pinecone import Pinecone
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = "forged-freedom-ai"
NAMESPACE = "women_steroids"

assert OPENROUTER_API_KEY, "OPENROUTER_API_KEY missing"
assert PINECONE_API_KEY, "PINECONE_API_KEY missing"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS_ROOT = REPO_ROOT / "transcripts"

EMBED_MODEL = "text-embedding-3-large"
BATCH = 32
SLEEP = 0.2

FEMALE_TERMS = re.compile(r"\b(women|woman|female|viril|virilization|androgen|masculin|voice|clit|irreversible)\b", re.I)

FILE_MARKER = re.compile(r"^=== FILE: (.+?) ===$", re.M)

def embed_batch(texts):
  r = requests.post(
    "https://openrouter.ai/api/v1/embeddings",
    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
    json={"model": EMBED_MODEL, "input": texts},
    timeout=60
  )
  r.raise_for_status()
  data = r.json()["data"]
  return [d["embedding"] for d in data]

def chunk_sentences(text, max_chars=900):
  # simple sentence-ish chunking
  parts = re.split(r"(?<=[\.\?\!])\s+", text.strip())
  buf = ""
  for p in parts:
    if len(buf) + len(p) + 1 <= max_chars:
      buf += (" " if buf else "") + p
    else:
      if len(buf) >= 200:
        yield buf
      buf = p
  if len(buf) >= 200:
    yield buf

def extract_episode_blocks(master_text):
  # Split by === FILE: name === markers. If none, treat entire text as one episode.
  markers = list(FILE_MARKER.finditer(master_text))
  if not markers:
    yield ("Unknown Episode", master_text)
    return

  for i, m in enumerate(markers):
    ep = m.group(1).strip()
    start = m.end()
    end = markers[i+1].start() if i+1 < len(markers) else len(master_text)
    yield (ep, master_text[start:end].strip())

def main():
  upserted = 0

  for channel_dir in TRANSCRIPTS_ROOT.iterdir():
    if not channel_dir.is_dir():
      continue

    podcast = channel_dir.name.replace("@", "")

    for master_file in sorted(channel_dir.glob("master_transcript*.txt")):
      text = master_file.read_text(encoding="utf-8", errors="ignore")

      for episode, ep_text in extract_episode_blocks(text):
        # Filter to female-related chunks only for this namespace
        chunks = []
        meta = []

        for chunk in chunk_sentences(ep_text, max_chars=900):
          if not FEMALE_TERMS.search(chunk):
            continue
          chunks.append(chunk)
          meta.append({
            "podcast": podcast,
            "episode": episode,
            "speaker": podcast,  # best available unless you have speaker extraction
            "text": chunk,
            "tags": ["female"]
          })

          if len(chunks) >= BATCH:
            vecs = embed_batch(chunks)
            vectors = []
            for v, mdata in zip(vecs, meta):
              vectors.append({
                "id": str(uuid.uuid4()),
                "values": v,
                "metadata": mdata
              })
            index.upsert(vectors=vectors, namespace=NAMESPACE)
            upserted += len(vectors)
            chunks, meta = [], []
            time.sleep(SLEEP)

        if chunks:
          vecs = embed_batch(chunks)
          vectors = []
          for v, mdata in zip(vecs, meta):
            vectors.append({
              "id": str(uuid.uuid4()),
              "values": v,
              "metadata": mdata
            })
          index.upsert(vectors=vectors, namespace=NAMESPACE)
          upserted += len(vectors)
          time.sleep(SLEEP)

      print(f"✅ Reindexed women namespace for: {podcast}")

  print(f"\n🔥 Done. Upserted {upserted} female-focused quote chunks into namespace '{NAMESPACE}'.\n")

if __name__ == "__main__":
  main()
