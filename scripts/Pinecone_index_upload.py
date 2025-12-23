#!/usr/bin/env python3
import os
import tiktoken
from pathlib import Path
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

INDEX = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if INDEX not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(INDEX)
enc = tiktoken.get_encoding("cl100k_base")

def chunk_text(text, max_tokens=3500):
    tokens = enc.encode(text)
    for i in range(0, len(tokens), max_tokens):
        yield enc.decode(tokens[i:i + max_tokens])

ROOT = Path.cwd() / "transcripts"
files = list(ROOT.rglob("*.txt"))

for f in files:
    text = f.read_text(errors="ignore")
    for i, chunk in enumerate(chunk_text(text)):
        emb = client.embeddings.create(
            model="text-embedding-3-large",
            input=chunk
        ).data[0].embedding

        index.upsert([{
            "id": f"{f.stem}-{i}",
            "values": emb,
            "metadata": {
                "channel": f.parent.name,
                "source": f.name,
                "chunk": i,
                "text": chunk[:1500]
            }
        }])

print("🎯 Index upload complete")
