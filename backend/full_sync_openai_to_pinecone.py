import os
import json
import time
import openai
import pinecone
from tqdm import tqdm
from pathlib import Path

# === CONFIG ===
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "us-east1-gcp")

# === INIT CLIENTS ===
openai.api_key = OPENAI_API_KEY
pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)

# Ensure index exists
if INDEX_NAME not in pinecone.list_indexes():
    print(f"🪴 Creating Pinecone index {INDEX_NAME} ...")
    pinecone.create_index(
        name=INDEX_NAME,
        dimension=1536,
        metric="cosine"
    )
index = pinecone.Index(INDEX_NAME)

# === HELPERS ===
def chunk_text(text, max_len=2000, overlap=200):
    """Split text into overlapping chunks for embeddings"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_len - overlap):
        chunk = " ".join(words[i:i + max_len])
        if chunk:
            chunks.append(chunk)
    return chunks

def embed_texts(texts):
    """Batch embed text via OpenAI embeddings API"""
    response = openai.embeddings.create(
        model="text-embedding-3-large",
        input=texts
    )
    return [d.embedding for d in response.data]

def collect_text_files(base_dirs):
    """Collect all transcript files from multiple sources"""
    all_files = []
    for base_dir in base_dirs:
        path = Path(base_dir)
        if not path.exists():
            continue
        for f in path.rglob("*.txt"):
            if "master_transcript" in f.name or "transcript" in f.name:
                all_files.append(f)
    return all_files

def load_openai_files():
    """Fetch file list from OpenAI storage"""
    try:
        files = openai.files.list()
        data_files = [f for f in files.data if f["filename"].endswith(".txt")]
        print(f"📦 Found {len(data_files)} files in OpenAI storage.")
        return data_files
    except Exception as e:
        print(f"⚠️ Could not access OpenAI storage: {e}")
        return []

def read_openai_file(file_id):
    """Download and read OpenAI file content"""
    try:
        file_content = openai.files.content(file_id)
        return file_content.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def push_to_pinecone(vectors):
    """Push batches of embeddings to Pinecone"""
    BATCH = 100
    for i in tqdm(range(0, len(vectors), BATCH), desc="📤 Uploading batches"):
        batch = vectors[i:i + BATCH]
        index.upsert(vectors=batch)
    print(f"✅ Uploaded {len(vectors)} vectors to Pinecone.")

# === MAIN ===
def main():
    print("🚀 Starting full sync from OpenAI → Pinecone")

    sources = [
        "transcripts",
        "split_transcripts",
        "backend",
        "fbf-data",
        "@ThinkBIGBodybuilding",
        "."
    ]

    # 1️⃣ Load all local transcript files
    local_files = collect_text_files(sources)
    print(f"📁 Found {len(local_files)} local transcript files.")

    # 2️⃣ Load OpenAI storage files
    openai_files = load_openai_files()
    print(f"☁️ Found {len(openai_files)} files in OpenAI cloud.")

    # 3️⃣ Merge all contents
    content_map = {}
    word_count_total = 0
    for f in tqdm(local_files, desc="📚 Reading local files"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            key = f.stem.lower()
            if key not in content_map:
                content_map[key] = text
                word_count_total += len(text.split())
        except Exception:
            pass

    for f in tqdm(openai_files, desc="☁️ Reading OpenAI files"):
        text = read_openai_file(f.id)
        key = f.filename.lower()
        if key not in content_map:
            content_map[key] = text
            word_count_total += len(text.split())

    print(f"🧩 Combined total unique transcripts: {len(content_map)}")
    print(f"🗣️ Total words across dataset: {word_count_total:,}")

    # 4️⃣ Chunk, embed, and upload
    all_vectors = []
    count = 0

    for key, text in tqdm(content_map.items(), desc="🧠 Processing transcripts"):
        chunks = chunk_text(text)
        embeddings = embed_texts(chunks)
        batch = [
            (f"{key}-{i}", emb, {"source": key})
            for i, emb in enumerate(embeddings)
        ]
        all_vectors.extend(batch)
        count += 1

        # Push in batches to avoid RAM overload
        if len(all_vectors) > 2000:
            push_to_pinecone(all_vectors)
            all_vectors = []

    # Final flush
    if all_vectors:
        push_to_pinecone(all_vectors)

    # 5️⃣ Display final Pinecone totals
    stats = index.describe_index_stats()
    total_vectors = stats.get("total_vector_count", 0)
    namespaces = list(stats.get("namespaces", {}).keys())

    print("\n📊 Pinecone Index Totals")
    print(f"🧠 Index: {INDEX_NAME}")
    print(f"📦 Namespaces: {namespaces if namespaces else ['default']}")
    print(f"🔢 Total vectors: {total_vectors:,}")
    print(f"🗣️ Total transcripts processed: {len(content_map)}")
    print(f"🧾 Approx. total words: {word_count_total:,}")
    print("✅ Full OpenAI → Pinecone sync complete!")

if __name__ == "__main__":
    main()
