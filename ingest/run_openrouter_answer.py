#!/usr/bin/env python3
"""
Ask Coach Bryan – Intent-Anchored Quote Retrieval (FINAL)

Design rules:
• Verbatim transcript quotes only
• Attribution required
• No paraphrasing
• No compound favoritism
• Question intent must be satisfied by the FINAL ANSWER SET,
  not necessarily by every individual quote
"""

from __future__ import annotations
import os, sys, json, re, hashlib
from typing import List, Dict, Any
import requests
from pinecone import Pinecone

# ==========================
# CONFIG
# ==========================

INDEX_NAME = "forged-freedom-ai"
TOP_K_PER_NAMESPACE = 40
MAX_QUOTES = 3

NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "default",
    "transcripts",
    ""  # legacy namespace (critical)
]

# ==========================
# UTILITIES
# ==========================

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def first(md: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = md.get(k)
        if v:
            return str(v).strip()
    return ""

# ==========================
# EMBEDDING
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
# INTENT EXTRACTION
# ==========================

def extract_anchors(question: str) -> Dict[str, List[str]]:
    q = normalize(question)
    anchors = {}

    if "tren" in q:
        anchors["compound"] = ["trenbolone", "tren"]

    if any(w in q for w in ["woman", "women", "female"]):
        anchors["population"] = ["woman", "women", "female"]

    if any(w in q for w in ["risk", "viril", "side", "irreversible"]):
        anchors["risk"] = [
            "viril", "masculin", "androgen",
            "voice", "deepening", "facial hair",
            "clitoral", "permanent", "irreversible"
        ]

    return anchors

def anchor_hits(text: str, anchors: Dict[str, List[str]]) -> Dict[str, bool]:
    blob = normalize(text)
    return {
        group: any(term in blob for term in terms)
        for group, terms in anchors.items()
    }

# ==========================
# RETRIEVAL
# ==========================

def retrieve_candidates(question: str) -> List[Dict[str, Any]]:
    anchors = extract_anchors(question)
    vector = embed_query(question)

    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    idx = pc.Index(INDEX_NAME)

    seen = set()
    candidates = []

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

            hits = anchor_hits(text, anchors)

            # Quote must satisfy AT LEAST ONE anchor
            if not any(hits.values()):
                continue

            norm = normalize(text)
            h = hash_text(norm)
            if h in seen:
                continue
            seen.add(h)

            candidates.append({
                "text": text.strip(),
                "score": m.get("score", 0),
                "hits": hits,
                "podcast": first(md, ["podcast", "show", "channel"]),
                "episode": first(md, ["episode", "title"]),
                "speaker": first(md, ["speaker", "host", "guest"]),
                "source": first(md, ["source", "file", "path"])
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates

# ==========================
# FINAL SELECTION (FULL INTENT COVERAGE)
# ==========================

def select_quotes(candidates: List[Dict[str, Any]],
                  anchors: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    selected = []
    covered = {k: False for k in anchors}

    for c in candidates:
        selected.append(c)
        for k, v in c["hits"].items():
            if v:
                covered[k] = True

        if all(covered.values()) or len(selected) >= MAX_QUOTES:
            break

    return selected

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

    anchors = extract_anchors(question)
    candidates = retrieve_candidates(question)
    quotes = select_quotes(candidates, anchors)

    print(format_answer(quotes))

if __name__ == "__main__":
    main()
