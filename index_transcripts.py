#!/usr/bin/env python3
import os, tiktoken
from openai import OpenAI
from pinecone import Pinecone

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("forged-freedom-ai")

ENC = tiktoken.get_encoding("cl100k_base")

ROOT = "split_transcripts"

def chunk_text(text, max_tokens=1500, overlap=100):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        chunk = " ".join(words[start:start+max_tokens])
        chunks.append(chunk)
        start += max_tokens - overlap
    return chunks

print("📚 Indexing split transcripts...\n")

for ch in os.listdir(ROOT):
    ch_path = os.path.join(ROOT, ch)
    if not os.path.isdir(ch_path): continue

    for file in os.listdir(ch_path):
        if not file.endswith(".txt"): continue
        fpath = os.path.join(ch_path, file)
        episode_name = os.path.splitext(file)[0]
        with open(fpath, "r") as f:
            text = f.read()

        chunks = chunk_text(text)
        print(f"🧩 {ch}/{file} → {len(chunks)} chunks")

        vectors = []
        for i, chunk in enumerate(chunks):
            emb = client.embeddings.create(input=chunk, model="text-embedding-3-large").data[0].embedding
            vectors.append({
                "id": f"{ch}_{episode_name}_{i}",
                "values": emb,
                "metadata": {
                    "channel": ch,
                    "show": ch.replace("@", ""),
                    "episode": episode_name,
                    "text": chunk
                }
            })
        index.upsert(vectors=vectors)

print("✅ All split episodes indexed successfully.")
