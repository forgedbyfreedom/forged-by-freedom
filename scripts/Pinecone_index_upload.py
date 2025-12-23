#!/usr/bin/env python3
"""
Uploads transcripts into Pinecone using OpenAI embeddings
"""

import os
import tiktoken
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(INDEX_NAME)

def chunk_text(text, max_tokens=3500):
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    for i in range(0, len(tokens), max_tokens):
        yield enc.decode(tokens[i:i + max_tokens])

TRANSCRIPTS = Path.cwd() / "transcripts_all"

for txt in TRANSCRIPTS.rglob("*.txt"):
    text = txt.read_text(errors="ignore")
    for i, chunk in enumerate(chunk_text(text)):
        emb = client.embeddings.create(
            model="text-embedding-3-large",
            input=chunk
        ).data[0].embedding

        index.upsert([{
            "id": f"{txt.parent.name}:{txt.stem}:{i}",
            "values": emb,
            "metadata": {
                "channel": txt.parent.name,
                "episode": txt.stem,
                "chunk": i,
                "text": chunk[:1500]
            }
        }])

print("🎯 Pinecone upload complete")
