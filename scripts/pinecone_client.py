from pathlib import Path
from dotenv import load_dotenv
import os
from pinecone import Pinecone

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

def get_index():
    key = os.getenv("PINECONE_API_KEY")
    name = os.getenv("PINECONE_INDEX_NAME")

    if not key or not name:
        raise RuntimeError("Missing Pinecone configuration")

    pc = Pinecone(api_key=key)
    return pc.Index(name)
