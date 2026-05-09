#!/usr/bin/env python3
"""Quick Pinecone retrieval test for bloodwork queries."""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("forged-freedom-ai")

QUERIES = [
    "My ALT is 180 and GGT is 120",
    "What bloodwork should I get before starting tren",
    "hematocrit 53% on 500mg test",
    "eGFR of 55 I weigh 240lbs",
    "prolactin 28 on deca",
    "LDL 165 HDL 22 on tren",
    "fasting glucose 118 on 4IU GH",
    "sleep apnea bodybuilding",
    "mental health on tren",
    "diuretics peak week safety",
]

for q in QUERIES:
    print(f"\n{'='*70}")
    print(f"QUERY: {q}")
    print(f"{'='*70}")
    emb = client.embeddings.create(model="text-embedding-3-large", input=q).data[0].embedding
    res = index.query(vector=emb, top_k=5, include_metadata=True, namespace="cycle_design_guides")
    for i, m in enumerate(res.matches):
        title = m.metadata.get("title", "?")[:60]
        text = m.metadata.get("text", "")[:120].replace("\n", " ")
        print(f"  [{i+1}] score={m.score:.4f} | {title}")
        print(f"      {text}...")
