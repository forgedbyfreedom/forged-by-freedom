import re
import unicodedata

def sanitize_id(text: str) -> str:
    """Convert filename to safe ASCII ID for Pinecone."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", text)
    return text

# === Sync transcripts ===
transcripts = sorted(glob.glob("transcripts/*.txt"))
print(f"📚 Found {len(transcripts)} transcript files to sync")

for path in tqdm(transcripts, desc="Uploading transcripts"):
    filename = os.path.basename(path)
    safe_id = sanitize_id(filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    chunks = chunk_text(text)
    vectors = []

    for i, chunk in enumerate(chunks):
        try:
            resp = client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk
            )
            embedding = resp.data[0].embedding
            vectors.append({
                "id": f"{safe_id}-{i}",
                "values": embedding,
                "metadata": {"source": filename, "chunk": i}
            })
        except Exception as e:
            print(f"⚠️ Skipping chunk {i} from {filename}: {e}")

    if vectors:
        index.upsert(vectors=vectors)
        print(f"✅ Uploaded {len(vectors)} chunks from {filename}")

print("🎉 All transcripts uploaded successfully to Pinecone!")
