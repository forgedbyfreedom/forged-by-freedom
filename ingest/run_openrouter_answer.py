#!/usr/bin/env python3
"""
Ask Coach Bryan – Intent-Anchored Quote Retrieval Engine

Key principles:
- Quote-only (verbatim spoken transcript text)
- Attribution required
- Retrieval bound to QUESTION INTENT, not semantic proximity
- No compound favoritism, no paraphrasing, no hallucination
"""

from __future__ import annotations
import os, sys, json, re, hashlib
import requests
from typing import List, Dict, Any
from pinecone import Pinecone

# ==========================
# CONFIG
# ==========================

INDEX_NAME = "forged-freedom-ai"
TOP_K_PER_NAMESPACE = 40
FINAL_QUOTES = 3

NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "default",
    "transcripts",
    ""   # legacy namespace (CRITICAL)
]

# ==========================
# UTILS
# ==========================

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def first(metadata: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = metadata.get(k)
        if v:
            return str(v).strip()
    return ""

# ==========================
# EMBEDDING (OpenRouter)
# ==========================

def embed_query(query: str) -> List[float]:
    resp = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"
        },
        json={
            "model": "text-embedding-3-large",
            "input": query
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]

# ==========================
# INTENT ANCHOR EXTRACTION
# ==========================

def extract_required_anchors(question: str) -> Dict[str, List[str]]:
    q = normalize(question)

    anchors = {}

    if "tren" in q:
        anchors["compound"] = ["trenbolone", "tren"]

    if any(w in q for w in ["woman", "women", "female"]):
        anchors["population"] = ["woman", "women", "female"]

    if any(w in q for w in ["risk", "viril", "masculin", "side effect", "irreversible"]):
        anchors["risk"] = [
            "viril", "masculin", "androgen",
            "voice", "clitoral", "facial hair",
            "irreversible", "permanent"
        ]

    return anchors

def satisfies_intent(text: str, anchors: Dict[str, List[str]]) -> bool:
    blob = normalize(text)
    for terms in anchors.values():
        if not any(t in blob for t in terms):
            return False
    return True

# ==========================
# RETRIEVAL
# ==========================

def retrieve(question: str) -> List[Dict[str, Any]]:
    anchors = extract_required_anchors(question)
    vector = embed_query(question)

    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    idx = pc.Index(INDEX_NAME)

    seen = set()
    results = []

    for ns in NAMESPACES:
        res = idx.query(
            vector=vector,
            top_k=TOP_K_PER_NAMESPACE,
            include_metadata=True,
            namespace=ns
        )

        for m in res.get("matches", []):
            md = m.get("metadata", {})
            text = first(md, ["text", "chunk", "content", "quote"])
            if not text:
                continue

            text_norm = normalize(text)
            if not satisfies_intent(text_norm, anchors):
                continue

            h = hash_text(text_norm)
            if h in seen:
                continue
            seen.add(h)

            results.append({
                "text": text.strip(),
                "score": m.get("score", 0),
                "podcast": first(md, ["podcast", "show", "channel"]),
                "episode": first(md, ["episode", "title"]),
                "speaker": first(md, ["speaker", "host", "guest"]),
                "source": first(md, ["source", "file", "path"])
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:FINAL_QUOTES]

# ==========================
# OUTPUT
# ==========================

def format_answer(quotes: List[Dict[str, Any]]) -> str:
    lines = ["Answer:"]
    for i, q in enumerate(quotes, 1):
        lines.append(
            f'{i}) "{q["text"]}" — {q["speaker"] or "Unknown Speaker"}, {q["podcast"] or "Unknown Podcast"}'
        )

    lines.append("\nSources:")
    for q in quotes:
        lines.extend([
            f'- Podcast: {q["podcast"] or "Unknown Podcast"}',
            f'  Episode: {q["episode"] or "Unknown Episode"}',
            f'  Speaker: {q["speaker"] or "Unknown Speaker"}',
            f'  Quote: "{q["text"]}"',
            ""
        ])

    return "\n".join(lines)

# ==========================
# MAIN
# ==========================

def main():
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise RuntimeError("No question provided")

    quotes = retrieve(question)
    print(format_answer(quotes))

if __name__ == "__main__":
    main()
