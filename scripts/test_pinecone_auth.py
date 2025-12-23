from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone
import os

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

print("Key loaded:", os.getenv("PINECONE_API_KEY")[:8])

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
print("Indexes:", pc.list_indexes().names())
