#!/usr/bin/env python3
"""
Forged By Freedom — GitHub → Pinecone Ingest (Manifest + Category Weight)
-----------------------------------------------------------------------
• Reads per-channel transcripts from ingest/channels/@Channel/*.txt
• Uses ingest/channel_manifest.yml to decide which channels to ingest + metadata
• Chunks text
• Creates embeddings
• Upserts to Pinecone (__default__)
• Serverless-safe: host-only
"""

import os, glob, hashlib
import yaml
from pinecone import Pinecone
from openai import OpenAI

# --- Required env vars ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST    = os.getenv("PINECONE_HOST")  # host-only for serverless
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")

if not PINECONE_API_KEY: raise RuntimeError("Missing PINECONE_API_KEY")
if not PINECONE_HOST:    raise RuntimeError("Missing PINECONE_HOST (required for serverless Pinecone)")
if not OPENAI_API_KEY:   raise RuntimeError("Missing OPENAI_API_KEY")

# IMPORTANT: strip whitespace/newlines from host (prevents the \n bug)
PINECONE_HOST = PINECONE_HOST.strip()

# --- Config ---
TRANSCRIPT_ROOT = "ingest/channels"
MANIFEST_PATH   = "ingest/channel_manifest.yml"
CHUNK_SIZE      = 1200
NAMESPACE       = "__default__"
EMBED_MODEL     = "text-embedding-3-large"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)
client = OpenAI(api_key=OPENAI_API_KEY)

def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        raise RuntimeError(f"Missing {MANIFEST_PATH}. Create it first.")
    with open(MANIFEST_PATH, "r") as f:
        m = yaml.safe_load(f) or {}
    channels = m.get("channels", [])
    # normalize into dict by channel name
    out = {}
    for c in channels:
        name = c.get("channel")
        if not name: 
            continue
        out[name] = {
            "enabled": bool(c.get("enabled", True)),
            "category": c.get("category", "unclassified"),
            "priority": int(c.get("priority", 50)),
        }
    return out

def chunk_text(text, size):
    for i in range(0, len(text), size):
        yield text[i:i+size]

def embed_texts(texts):
    res = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in res.data]

def stable_id(channel, source, chunk):
    h = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
    return f"{channel}|{source}|{h}"

def infer_series_and_title(filename: str):
    """
    Helps with ThinkBig sub-series visibility.
    If your filenames contain series tokens, we preserve them.
    Example: "Blood_Sweat_Gear_Ep123.txt" -> series="Blood Sweat Gear"
    """
    base = os.path.splitext(filename)[0]
    # crude heuristics: treat prefix before first "__" as series if present
    if "__" in base:
        series, title = base.split("__", 1)
        return series.replace("_", " ").strip(), title.replace("_", " ").strip()
    return "", base.replace("_", " ").strip()

def ingest():
    manifest = load_manifest()

    # find channel dirs on disk
    channel_dirs = sorted([d for d in glob.glob(f"{TRANSCRIPT_ROOT}/@*") if os.path.isdir(d)])
    if not channel_dirs:
        print("⚠️ No channel directories found under ingest/channels/@*")
        return 0

    total_vectors = 0
    print("🔥 Starting Pinecone ingest\n")

    for channel_dir in channel_dirs:
        channel = os.path.basename(channel_dir)

        cfg = manifest.get(channel)
        if not cfg:
            print(f"⏭️  {channel} not in manifest (skipping)")
            continue
        if not cfg["enabled"]:
            print(f"⏭️  {channel} disabled in manifest (skipping)")
            continue

        category = cfg["category"]
        priority = cfg["priority"]

        print(f"📘 Channel: {channel}  | category={category} priority={priority}")

        txt_paths = sorted(glob.glob(f"{channel_dir}/*.txt"))
        if not txt_paths:
            print("   ⚠ No .txt files found")
            continue

        for path in txt_paths:
            source = os.path.basename(path)

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = (f.read() or "").strip()

            if not text:
                print(f"   ⚠ {source} empty (skipped)")
                continue

            series, title = infer_series_and_title(source)

            chunks = list(chunk_text(text, CHUNK_SIZE))
            embeddings = embed_texts(chunks)

            vectors = []
            for chunk, emb in zip(chunks, embeddings):
                vid = stable_id(channel, source, chunk)
                vectors.append({
                    "id": vid,
                    "values": emb,
                    "metadata": {
                        "channel": channel,
                        "category": category,
                        "priority": priority,
                        "source": source,
                        "series": series,
                        "title": title,
                        "text": chunk
                    }
                })

            index.upsert(vectors=vectors, namespace=NAMESPACE)
            total_vectors += len(vectors)
            print(f"   ✔ {source} → {len(vectors)} vectors")

    print(f"\n✅ Ingest complete — total vectors upserted: {total_vectors}")
    return total_vectors

if __name__ == "__main__":
    ingest()

