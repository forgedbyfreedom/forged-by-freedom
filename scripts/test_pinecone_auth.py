import os
from pathlib import Path
from pinecone import Pinecone
from dotenv import load_dotenv

# FORCE load .env
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

api_key = os.getenv("PINECONE_API_KEY")
print("API KEY LOADED:", bool(api_key))

if not api_key:
    raise RuntimeError("PINECONE_API_KEY is missing")

pc = Pinecone(api_key=api_key)

# This call will FAIL if auth is wrong
indexes = pc.list_indexes()
print("Pinecone indexes:", indexes)
