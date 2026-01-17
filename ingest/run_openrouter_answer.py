#!/usr/bin/env python3
"""
Ask Coach Bryan – Intent-Anchored Quote Retrieval (MANDATORY + COVERAGE)

Rules:
• Verbatim transcript quotes only
• Attribution required
• If a compound is explicitly named in the question, it is MANDATORY per quote
• Population / risk anchors may be satisfied across the final answer set
• No semantic drift, no compound favoritism, no paraphrasing
"""

from __future__ import annotations

import os
import sys
import re
import json
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

NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "default",
    "transcripts",
    ""  # legacy namespace
]

OPENROUTER_EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")


# ==========================================================
# UTILS
# ==========================================================

def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def normalize(text: str) -> str:
    return normalize_ws(text.lower())

def hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def first(md: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = md.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""

def compile_patterns(terms: List[str]) -> List[re.Pattern]:
    """
    Compile regex patterns.
    - 'viril*' => prefix match
    - exact tokens are word-boundary protected
    """
    pats: List[re.Pattern] = []
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue

        if t.endswith("*"):
            stem = re.escape(t[:-1])
            pats.append(re.compile(rf"\b{stem}\w*\b", re.IGNORECASE))
        else:
            esc = re.escape(t)
            pats.append(re.compile(rf"(?<!\w){esc}(?!\w)", re.IGNORECASE))
    return pats


# ==========================================================
# EMBEDDING
# ==========================================================

def embed_query(query: str) -> List[float]:
    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENROUTER_EMBED_MODEL,
            "input": query
        },
        timeout=45
    )
    resp.raise_for_status()
    emb = resp.json()["data"][0]["embedding"]
    if not emb:
        raise RuntimeError("Empty embedding returned")
    return emb


# ==========================================================
# INTENT ANCHORS
# ==========================================================

def extract_anchors(question: str) -> Dict[str, Dict[str, Any]]:
    """
    Returns anchor config:
    {
      "compound": {"terms": [...], "required": True},
      "population": {"terms": [...], "required": False},
      "risk": {"terms": [...], "required": False}
    }
    """
    q = question.lower()
    anchors: Dict[str, Dict[str, Any]] = {}

    # Mandatory compound anchor
    if "tren" in q:
        anchors["compound"] = {
            "terms": ["trenbolone", "tren"],
            "required": True
        }

    # Population (coverage)
    if any(w in q for w in ["woman", "women", "female", "girl", "girls"]):
        anchors["population"] = {
            "terms": ["woman", "women", "female", "girl", "girls"],
            "required": False
        }

    # Risk / virilization (coverage)
    if any(w in q for w in ["viril", "mascul", "androgen", "risk", "irreversible", "permanent"]):
        anchors["risk"] = {
            "terms": [
                "viril*",
                "mascul*",
                "androgen*",
                "voice",
                "clitoral", "clit",
                "facial hair", "beard",
                "irreversible", "permanent"
            ],
            "required": False
        }

    return anchors


def build_matchers(anchors: Dict[str, Dict[str, Any]]) -> Dict[str, List[re.Pattern]]:
    return {
        k: compile_patterns(v["terms"])
        for k, v in anchors.items()
    }


def anchor_hits(text: str, matchers: Dict[str, List[re.Pattern]]) -> Dict[str, bool]:
    blob = text.lower()
    return {
        k: any(p.search(blob) for p in pats)
        for k, pats in matchers.items()
    }


def reject_false_tren(text: str) -> bool:
    """
    Prevent Turinabol / Trenoball false positives.
    """
    t = text.lower()
    if re.search(r"\btrenoball\b", t):
        return True
    if re.search(r"\bt-?bol\b", t) or re.search(r"\bturinabol\b", t):
        if not re.search(r"\btrenbolone\b", t):
            return True
    return False


# ==========================================================
# RETRIEVAL
# ==========================================================

def retrieve_candidates(question: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    anchors = extract_anchors(question)
    matchers = build_matchers(anchors)
    vector = embed_query(question)

    idx = Pinecone(api_key=os.environ["PINECONE_API_KEY"]).Index(INDEX_NAME)

    seen = set()
    candidates: List[Dict[str, Any]] = []

    for ns in NAMESPACES:
        res = idx.query(
            vector=vector,
            top_k=TOP_K_PER_NAMESPACE,
            include_metadata=True,
            namespace=ns
        )

        for m in res.get("matches", []) or []:
            md = m.get("metadata", {}) or {}
            text = first(md, ["text", "chunk", "content", "quote", "transcript", "passage"])
            if not text:
                continue

            text = normalize_ws(text)
            norm = text.lower()
            h = hash_text(norm)
            if h in seen:
                continue
            seen.add(h)

            hits = anchor_hits(text, matchers)

            # Enforce REQUIRED anchors per quote
            reject = False
            for k, cfg in anchors.items():
                if cfg["required"] and not hits.get(k):
                    reject = True
                    break
            if reject:
                continue

            # Must hit at least one anchor
            if anchors and not any(hits.values()):
                continue

            # Reject false tren matches
            if "compound" in anchors and reject_false_tren(text):
                continue

            candidates.append({
                "text": text,
                "score": float(m.get("score") or 0.0),
                "hits": hits,
                "podcast": first(md, ["podcast", "show", "channel", "series"]),
                "episode": first(md, ["episode", "title", "episode_title", "video_title", "name"]),
                "speaker": first(md, ["speaker", "host", "guest", "author"]),
                "timestamp": first(md, ["timestamp", "time", "start_time", "ts", "start"]),
                "source": first(md, ["source", "file", "path", "url"]),
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates, anchors


# ==========================================================
# SELECTION (Coverage-aware)
# ==========================================================

def select_quotes(candidates: List[Dict[str, Any]],
                  anchors: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:

    if not candidates:
        return []

    covered = {k: False for k, v in anchors.items() if not v["required"]}
    selected: List[Dict[str, Any]] = []
    remaining = candidates[:]

    def gain(c: Dict[str, Any]) -> int:
        return sum(
            1 for k in covered
            if not covered[k] and c["hits"].get(k)
        )

    while remaining and len(selected) < MAX_QUOTES:
        best_i = -1
        best_key = (-1, -1.0)

        for i, c in enumerate(remaining):
            key = (gain(c), c["score"])
            if key > best_key:
                best_key = key
                best_i = i

        if best_i == -1:
            break

        chosen = remaining.pop(best_i)
        selected.append(chosen)

        for k in covered:
            if chosen["hits"].get(k):
                covered[k] = True

        if all(covered.values()):
            break

    return selected


# ==========================================================
# OUTPUT
# ==========================================================

def format_answer(quotes: List[Dict[str, Any]]) -> str:
    lines = ["Answer:"]
    for i, q in enumerate(quotes, 1):
        lines.append(
            f'{i}) "{q["text"]}" — {q["speaker"] or "Unknown Speaker"}, {q["podcast"] or "Unknown Podcast"}'
        )

    lines.append("")
    lines.append("Sources:")
    for q in quotes:
        lines.append(f"- Podcast: {q['podcast'] or 'Unknown Podcast'}")
        lines.append(f"  Episode: {q['episode'] or 'Unknown Episode'}")
        lines.append(f"  Speaker: {q['speaker'] or 'Unknown Speaker'}")
        if q.get("timestamp"):
            lines.append(f"  Timestamp: {q['timestamp']}")
        if q.get("source"):
            lines.append(f"  Source: {q['source']}")
        lines.append(f'  Quote: "{q["text"]}"')
    return "\n".join(lines)


# ==========================================================
# MAIN
# ==========================================================

def main():
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise RuntimeError("No question provided")

    candidates, anchors = retrieve_candidates(question)
    quotes = select_quotes(candidates, anchors)
    print(format_answer(quotes))

if __name__ == "__main__":
    main()
