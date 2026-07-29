import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from pinecone import Pinecone

# =============================
# CONFIG
# =============================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")

if not PINECONE_API_KEY:
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# =============================
# CONNECT
# =============================
pc = Pinecone(api_key=PINECONE_API_KEY)

print("🔎 Pinecone Index Verification")
print("=" * 50)

# =============================
# INDEX CHECK
# =============================
indexes = pc.list_indexes().names()
if INDEX_NAME not in indexes:
    raise RuntimeError(f"❌ Index '{INDEX_NAME}' not found")

index = pc.Index(INDEX_NAME)

# =============================
# STATS
# =============================
stats = index.describe_index_stats()

total_vectors = stats.get("total_vector_count", 0)
namespaces = stats.get("namespaces", {})

print(f"📦 Index: {INDEX_NAME}")
print(f"📊 Total vectors: {total_vectors}")
print()

print("📂 Namespaces:")
if not namespaces:
    print("⚠️  No namespaces found")
else:
    for ns, data in namespaces.items():
        count = data.get("vector_count", 0)
        print(f"  • {ns or '[default]'}: {count} vectors")

print()
print("✅ Pinecone verification complete")
