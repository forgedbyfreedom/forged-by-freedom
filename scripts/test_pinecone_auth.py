import os
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv(Path(".env"))

api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME")

print("API key loaded:", bool(api_key))
print("Index name:", index_name)

pc = Pinecone(api_key=api_key)

indexes = pc.list_indexes()
print("Indexes:", [i["name"] for i in indexes])

assert index_name in [i["name"] for i in indexes], "Index name not found!"
print("✅ Pinecone auth + index OK")
