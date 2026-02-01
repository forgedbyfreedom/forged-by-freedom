#!/usr/bin/env python3
"""
Forged By Freedom — Pinecone Ingest
-----------------------------------
Ingests corrected transcripts into Pinecone with rich metadata:
- channel: @handle extracted from path
- title: episode title parsed from filename
- text: actual chunk content (for retrieval)
- source: normalized source path
- video_id: YouTube video ID
"""

import os
import re
import sys
import time
import hashlib
from pathlib import Path

import tiktoken
from openai import OpenAI
from pinecone import Pinecone

# ---------------- CONFIG ----------------
BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
EMBED_MODEL = "text-embedding-3-large"

CHUNK_TOKENS = 3000
EMBED_BATCH = 16
SLEEP_BETWEEN_BATCHES = 0.3

# ----------------------------------------

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("❌ OPENAI_API_KEY not set")

if not os.getenv("PINECONE_API_KEY"):
    raise RuntimeError("❌ PINECONE_API_KEY not set")

client = OpenAI()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(INDEX_NAME)

tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))


def chunk_text(text: str):
    """Split text into chunks of CHUNK_TOKENS size."""
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), CHUNK_TOKENS):
        yield tokenizer.decode(tokens[i:i + CHUNK_TOKENS])


def embed_batch(texts):
    """Embed a batch of texts using OpenAI."""
    res = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]


def extract_channel(path: Path) -> str:
    """Extract @channel from file path."""
    for part in path.parts:
        if part.startswith("@"):
            return part
    return "unknown"


def extract_video_id(filename: str) -> str:
    """Extract YouTube video ID from filename like 'Title [VIDEO_ID].txt'."""
    match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', filename)
    return match.group(1) if match else ""


def extract_title(filename: str) -> str:
    """Extract episode title from filename."""
    # Remove extension
    name = filename.replace(".txt", "")
    # Remove video ID bracket
    name = re.sub(r'\s*\[[a-zA-Z0-9_-]{11}\]$', '', name)
    return name.strip()


def extract_speaker(title: str, channel: str) -> str:
    """Extract speaker name from title or channel."""
    # Common patterns: "Topic | Speaker Name" or "Speaker Name: Topic"

    # Pattern: "Title | Dr. Name" or "Title ｜ Dr. Name"
    pipe_match = re.search(r'[|｜]\s*(.+)$', title)
    if pipe_match:
        speaker = pipe_match.group(1).strip()
        # Check if it looks like a name (has Dr., PhD, etc. or capitalized words)
        if re.search(r'(Dr\.|PhD|MD|Professor|\b[A-Z][a-z]+\s+[A-Z])', speaker):
            return speaker

    # Pattern: "Dr. Name: Topic" or "Name, PhD: Topic"
    colon_match = re.match(r'^([^:]+(?:Dr\.|PhD|MD)[^:]*?):\s', title)
    if colon_match:
        return colon_match.group(1).strip()

    # Pattern: "Dr. Name on Topic" or "Name, PhD on Topic"
    on_match = re.match(r'^(.+?(?:Dr\.|PhD|MD).+?)\s+on\s+', title, re.IGNORECASE)
    if on_match:
        return on_match.group(1).strip()

    # Known channel-to-speaker mappings
    channel_speakers = {
        "@FoundMyFitness": "Dr. Rhonda Patrick",
        "@PeterAttiaMD": "Dr. Peter Attia",
        "@hubermanlab": "Dr. Andrew Huberman",
        "@DrGabrielleLyon": "Dr. Gabrielle Lyon",
        "@MorePlatesMoreDates": "Derek (MPMD)",
        "@GregDoucette": "Greg Doucette",
        "@JeffNippard": "Jeff Nippard",
        "@ChrisBumstead": "Chris Bumstead",
        "@sam_sulek": "Sam Sulek",
        "@Biolayne": "Dr. Layne Norton",
        "@vigoroussteve": "Vigorous Steve",
        "@ThinkBIGBodybuilding": "Dave Palumbo",
        "@rxmuscle": "Dave Palumbo",
        "@RenaissancePeriodization": "Dr. Mike Israetel",
        "@BarbellMedicine": "Dr. Jordan Feigenbaum",
        "@DavidGoggins": "David Goggins",
        "@JockoPodcastOfficial": "Jocko Willink",
    }

    if channel in channel_speakers:
        return channel_speakers[channel]

    return "unknown"


def get_namespace(channel: str, path: Path) -> str:
    """Determine namespace based on channel or path."""
    # Check if it's in a specific namespace folder
    path_str = str(path).lower()

    # Map channels to namespaces
    namespace_map = {
        "@MorePlatesMoreDates": "anabolic_bodybuilding_priority",
        "@GregDoucette": "anabolic_bodybuilding_priority",
        "@vigoroussteve": "anabolic_bodybuilding_priority",
        "@FouadAbiad": "anabolic_bodybuilding_priority",
        "@ThinkBIGBodybuilding": "thinkbig_priority",
        "@FoundMyFitness": "biohacking",
        "@hubermanlab": "biohacking",
        "@PeterAttiaMD": "medical_primary",
        "@DrGabrielleLyon": "medical_primary",
        "@BarbellMedicine": "medical_primary",
        "@JeffNippard": "sports_nutrition",
        "@RenaissancePeriodization": "sports_nutrition",
        "@Biolayne": "sports_nutrition",
        "@DavidGoggins": "sports_psych",
        "@JockoPodcastOfficial": "sports_psych",
    }

    if channel in namespace_map:
        return namespace_map[channel]

    return "transcripts"


def ingest():
    """Main ingest function with rich metadata."""
    print("\n🔍 INGEST STARTUP")
    print(f"• CHANNELS_DIR: {CHANNELS_DIR}")
    print(f"• Pinecone index: {INDEX_NAME}")
    print(f"• Embedding model: {EMBED_MODEL}")
    print(f"• Chunk tokens: {CHUNK_TOKENS}")

    # Get all txt files, excluding master transcripts
    txt_files = [
        f for f in CHANNELS_DIR.rglob("*.txt")
        if not f.name.startswith("master_transcript")
        and not f.name.startswith(".")
    ]

    total_files = len(txt_files)
    print(f"• Episodes to ingest: {total_files}")
    print("🚀 BEGIN INGEST\n")

    episode_count = 0
    word_count = 0
    chunk_count = 0
    errors = []

    for txt in txt_files:
        try:
            text = txt.read_text(errors="ignore").strip()
            if not text:
                continue

            words = len(text.split())
            chunks = list(chunk_text(text))

            # Extract metadata
            channel = extract_channel(txt)
            title = extract_title(txt.name)
            video_id = extract_video_id(txt.name)
            speaker = extract_speaker(title, channel)
            namespace = get_namespace(channel, txt)
            source = f"transcripts/{channel}/{txt.name}"

            vectors = []
            for chunk_idx, chunk_content in enumerate(chunks):
                # Create unique ID from content hash
                vec_id = hashlib.sha1(
                    f"{channel}:{video_id}:{chunk_idx}:{chunk_content[:100]}".encode()
                ).hexdigest()

                vectors.append({
                    "id": vec_id,
                    "values": None,  # Will be filled by embedding
                    "metadata": {
                        "text": chunk_content[:8000],  # Pinecone metadata limit
                        "channel": channel,
                        "speaker": speaker,
                        "title": title,
                        "source": source,
                        "video_id": video_id,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                        "word_count": words
                    }
                })

            # Embed and upsert in batches
            for i in range(0, len(vectors), EMBED_BATCH):
                batch = vectors[i:i + EMBED_BATCH]
                texts_to_embed = [v["metadata"]["text"] for v in batch]

                embeddings = embed_batch(texts_to_embed)

                for vec, emb in zip(batch, embeddings):
                    vec["values"] = emb

                # Upsert to namespace
                index.upsert(vectors=batch, namespace=namespace)
                chunk_count += len(batch)
                time.sleep(SLEEP_BETWEEN_BATCHES)

            episode_count += 1
            word_count += words

            print(f"✅ [{episode_count}/{total_files}] {channel} | {speaker} | {title[:40]}... | {len(chunks)} chunks")

        except Exception as e:
            errors.append((txt.name, str(e)))
            print(f"❌ Failed: {txt.name} — {e}")

    print("\n" + "=" * 60)
    print("✅ INGEST COMPLETE")
    print(f"📚 Episodes: {episode_count:,}")
    print(f"🧩 Chunks: {chunk_count:,}")
    print(f"📝 Words: {word_count:,}")

    if errors:
        print(f"\n⚠️  {len(errors)} errors:")
        for name, err in errors[:10]:
            print(f"   • {name}: {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more")


if __name__ == "__main__":
    ingest()
