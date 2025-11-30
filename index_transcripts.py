#!/usr/bin/env python3
import os, time
from tqdm import tqdm
from openai import OpenAI
import pinecone

# === Setup ===
client = OpenAI()
pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment="us-east1-gcp")
index_name = "forged-freedom-ai"

# Create index if needed
if index_name not in pinecone.list_indexes().names():
    pinecone.create_index(name=index_name, dimension=1536, metric="cosine")

index = pinecone.Index(index_name)

# === Ingest all transcripts ===
base_dir = os.getcwd()
docs = []

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.startswith("master_transcript") and file.endswith(".txt"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                if len(text.strip()) > 0:
                    docs.append((path, text))

print(f"📚 Found {len(docs)} transcripts")

# === Embed and upload ===
for path, text in tqdm(docs):
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    for i, chunk in enumerate(chunks):
        emb = client.embeddings.create(input=chunk, model="text-embedding-3-small").data[0].embedding
        index.upsert(vectors=[{
            "id": f"{path}-{i}",
            "values": emb,
            "metadata": {"source": path, "text": chunk}
        }])
        time.sleep(0.1)

print("✅ Indexing complete — ready for search.")
