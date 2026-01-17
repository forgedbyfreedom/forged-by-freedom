#!/usr/bin/env python3
"""
Ask Coach Bryan – Quote Retrieval with Context Window Expansion

Rules:
• Verbatim transcript quotes only
• Attribution required
• Explicit compound questions enforce mandatory compound presence
• Coverage anchors (women / virilization) may be satisfied by adjacent chunks
• Context expansion is LIMITED and SAFE (±N chunks, same source only)
"""

from __future__ import annotations

import os
import sys
import re
import hashlib
from typing import List, Dict, Any, Tuple

import requests
from pinecone import Pinecone

# ==========================================================
# CONFIG
# ==========================================================

INDEX_NAME = os.getenv("PINECONE_INDEX", "forged-freedom-ai")
TOP_K_PER_NAMESPACE = int(os.getenv("FBF_TOPK_PER_NAMESPACE", "80"))
MAX_QUOTES = int(os.getenv("FBF_FINAL_QUOTES", "3"))
WINDOW_RADIUS = int(os.getenv("FBF_WINDOW_RADIUS", "2"))  # ± chunks

NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "default",
    "transcripts",
    ""
]

OPENROUTER_EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")

# ==========================================================
# UTILS
# ==========================================================

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def first(md: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = md.get(k)
        if v:
            return str(v).strip()
    return ""

def compile_patterns(terms: List[str]) -> List[re.Pattern]:
    pats = []
    for t in terms:
        if t.endswith("*"):
            pats.append(re.compile(rf"\b{re.escape(t[:-1])}\w*\b", re.I))
        else:
            pats.append(re.compile(rf"(?<!\w){re.escape(t)}(?!\w)", re.I))
    return pats

# ==========================================================
# EMBEDDING
# ==========================================================

def embed_query(q: str) -> List[float]:
    r = requests.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"
        },
        json={"model": OPENROUTER_EMBED_MODEL, "input": q},
        timeout=45
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]

# ==========================================================
# INTENT
# ==========================================================

def extract_anchors(q: str) -> Dict[str, Dict[str, Any]]:
    q = q.lower()
    anchors = {}

    if "tren" in q:
        anchors["compound"] = {
            "terms": ["trenbolone", "tren"],
            "required": True
        }

    if any(w in q for w in ["woman", "women", "female"]):
        anchors["population"] = {
            "terms": ["woman", "women", "female"],
            "required": False
        }

    if any(w in q for w in ["viril", "androgen", "mascul", "risk"]):
        anchors["risk"] = {
            "terms": ["viril*", "androgen*", "mascul*", "voice", "clitoral", "permanent"],
            "required": False
        }

    return anchors

def build_matchers(anchors):
    return {k: compile_patterns(v["terms"]) for k, v in anchors.items()}

def hits(text: str, matchers) -> Dict[str, bool]:
    t = text.lower()
    return {k: any(p.search(t) for p in pats) for k, pats in matchers.items()}

# ==========================================================
# RETRIEVAL + WINDOWING
# ==========================================================

def retrieve(question: str):
    anchors = extract_anchors(question)
    matchers = build_matchers(anchors)
    vec = embed_query(question)

    idx = Pinecone(api_key=os.environ["PINECONE_API_KEY"]).Index(INDEX_NAME)

    primary_chunks = []
    chunk_map = {}

    for ns in NAMESPACES:
        res = idx.query(vector=vec, top_k=TOP_K_PER_NAMESPACE, include_metadata=True, namespace=ns)
        for m in res.get("matches", []):
            md = m["metadata"]
            text = first(md, ["text", "chunk", "content", "quote"])
            if not text:
                continue

            key = first(md, ["source", "file", "path"])
            pos = md.get("chunk_index")

            if key and pos is not None:
                chunk_map.setdefault(key, {})[pos] = text

            h = hits(text, matchers)

            # enforce mandatory anchors
            if any(cfg["required"] and not h.get(k) for k, cfg in anchors.items()):
                continue

            if any(h.values()):
                primary_chunks.append({
                    "text": text.strip(),
                    "hits": h,
                    "source": key,
                    "pos": pos,
                    "meta": md
                })

    # window expansion
    expanded = []
    seen = set()

    for c in primary_chunks:
        expanded.append(c)
        seen.add(hash_text(c["text"]))

        if c["source"] and c["pos"] is not None:
            for i in range(c["pos"] - WINDOW_RADIUS, c["pos"] + WINDOW_RADIUS + 1):
                if i == c["pos"]:
                    continue
                t = chunk_map.get(c["source"], {}).get(i)
                if t:
                    h = hits(t, matchers)
                    k = hash_text(t)
                    if k not in seen:
                        expanded.append({
                            "text": t.strip(),
                            "hits": h,
                            "source": c["source"],
                            "pos": i,
                            "meta": c["meta"]
                        })
                        seen.add(k)

    return expanded, anchors

# ==========================================================
# SELECTION
# ==========================================================

def select_quotes(quotes, anchors):
    covered = {k: False for k, v in anchors.items() if not v["required"]}
    selected = []

    for q in quotes:
        selected.append(q)
        for k in covered:
            if q["hits"].get(k):
                covered[k] = True
        if all(covered.values()) or len(selected) >= MAX_QUOTES:
            break

    return selected

# ==========================================================
# OUTPUT
# ==========================================================

def format_answer(quotes):
    lines = ["Answer:"]
    for i, q in enumerate(quotes, 1):
        lines.append(f'{i}) "{q["text"]}"')

    lines.append("\nSources:")
    for q in quotes:
        md = q["meta"]
        lines.append(f'- Source: {first(md, ["source", "file", "path"])}')
        lines.append(f'  Quote: "{q["text"]}"')

    return "\n".join(lines)

# ==========================================================
# MAIN
# ==========================================================

def main():
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise RuntimeError("No question provided")

    quotes, anchors = retrieve(question)
    final = select_quotes(quotes, anchors)
    print(format_answer(final))

if __name__ == "__main__":
    main()
