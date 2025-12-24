from pathlib import Path
from dotenv import load_dotenv
import os
from pinecone import Pinecone

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
print("Indexes:", pc.list_indexes().names())
