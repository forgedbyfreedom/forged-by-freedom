# scripts/pinecone_client.py

import os
import pinecone

def get_pinecone_index():
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")

    if not api_key or not index_name:
        raise RuntimeError("PINECONE_API_KEY or PINECONE_INDEX_NAME not set")

    pc = pinecone.Pinecone(api_key=api_key)
    return pc.Index(index_name)
