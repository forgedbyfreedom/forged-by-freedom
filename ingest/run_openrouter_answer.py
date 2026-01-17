#!/usr/bin/env python3
"""
Ask Coach Bryan – Intent-Anchored Quote Retrieval (Coverage-Aware)

Fixes:
- Embed query before Pinecone search
- Query multiple namespaces (including legacy "")
- Intent anchors are matched with regex/token boundaries (prevents "Trenoball" => "tren" false hits)
- Candidate quotes can match PARTS of intent
- Final selection is COVERAGE-AWARE (greedy set cover): picks quotes that add missing anchors first
- Quote-only output with attribution fields (best-effort; metadata mapping can be tuned later)
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

# ==========================
# CONFIG
# ==========================

INDEX_NAME = os.getenv("PINECONE_INDEX", "forged-freedom-ai")
TOP_K_PER_NAMESPACE = int(os.getenv("FBF_TOPK_PER_NAMESPACE", "60"))
MAX_QUOTES = int(os.getenv("FBF_FINAL_QUOTES", "3"))

NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "default",
    "transcripts",
    ""  # legacy namespace (critical)
]

OPENROUTER_EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")


# ==========================
# UTILITIES
# ==========================

def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

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
    Compile robust patterns. We treat terms as fragments and enforce word-ish boundaries.
    Example: "tren" should match "tren " or "tren." but NOT "trenoball".
    """
    patterns: List[re.Pattern] = []
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue

        # If term looks like a stem (viril, masculin), allow prefix matching at word boundary.
        if t.endswith("*"):
            stem = re.escape(t[:-1])
            patterns.append(re.compile(rf"\b{stem}\w*\b", re.IGNORECASE))
            continue

        # Default: exact word-ish match
        # \b doesn't work perfectly with hyphens; allow hyphen/space separation.
        esc = re.escape(t)
        patterns.append(re.compile(rf"(?<!\w){esc}(?!\w)", re.IGNORECASE))
    return patterns


# ==========================
# EMBEDDING (OpenRouter)
# ==========================

def embed_query(query: str) -> List[float]:
    api_key = os.environ["OPENROUTER_API_KEY"]
    url = f"{OPENROUTER_BASE_URL}/embeddings"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Optional OpenRouter headers if you use them
    referer = os.getenv("OPENROUTER_SITE_URL") or os.getenv("OPENROUTER_HTTP_REFERER") or os.getenv("HTTP_REFERER")
    title = os.getenv("OPENROUTER_APP_NAME") or os.getenv("OPENROUTER_X_TITLE")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    resp = requests.post(
        url,
        headers=headers,
        json={"model": OPENROUTER_EMBED_MODEL, "input": query},
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    emb = data["data"][0]["embedding"]
    if not isinstance(emb, list) or not emb:
        raise RuntimeError("OpenRouter embeddings returned empty embedding")
    return emb


# ==========================
# INTENT ANCHORS (Question-driven)
# ==========================

def extract_anchors(question: str) -> Dict[str, List[str]]:
    """
    Anchors are derived from the question.
    We use 'stem*' for prefix/stem matching (compiled via compile_patterns).
    """
    q = question.lower()

    anchors: Dict[str, List[str]] = {}

    # Compound
    if "tren" in q:
        # Require trenbolone OR standalone tren token.
        anchors["compound"] = ["trenbolone", "tren"]

    # Population
    if any(w in q for w in ["woman", "women", "female", "girls"]):
        anchors["population"] = ["woman", "women", "female", "girl", "girls"]

    # Risk / virilization
    if any(w in q for w in ["viril", "virilization", "mascul", "androgen", "risk", "irreversible", "permanent"]):
        anchors["risk"] = [
            "viril*",          # viril, virilization
            "mascul*",         # masculinize, masculinity
            "androgen*",       # androgenic, androgenicity
            "voice",           # voice deepening
            "clitoral", "clit",
            "facial hair", "beard",
            "irreversible", "permanent",
        ]

    return anchors


def build_anchor_matchers(anchors: Dict[str, List[str]]) -> Dict[str, List[re.Pattern]]:
    return {k: compile_patterns(v) for k, v in anchors.items()}


def anchor_hits(text: str,
                matchers: Dict[str, List[re.Pattern]]) -> Dict[str, bool]:
    """
    Returns which anchor groups are satisfied by this text.
    """
    blob = text.lower()
    hits: Dict[str, bool] = {}
    for group, pats in matchers.items():
        hits[group] = any(p.search(blob) for p in pats)
    return hits


def reject_false_tren_hits(text: str, hits: Dict[str, bool]) -> bool:
    """
    Prevent common false positives where 'tren' is contained inside other compound names.
    Example: 'Trenoball' (Turinabol) shouldn't count as trenbolone.
    """
    if not hits.get("compound"):
        return False

    blob = text.lower()

    # If it contains "trenoball" or "treno-bol" etc, treat as NOT trenbolone.
    if re.search(r"\btreno-?ball\b", blob) or re.search(r"\btrenoball\b", blob):
        return True

    # Turinabol / T-bol segments sometimes include "Trenoball" transcription errors.
    if re.search(r"\bt-?bol\b", blob) or re.search(r"\bturinabol\b", blob):
        # Only reject if NO explicit trenbolone mention
        if not re.search(r"\btrenbolone\b", blob):
            return True

    return False


# ==========================
# RETRIEVAL
# ==========================

def pinecone_index():
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    return pc.Index(INDEX_NAME)


def retrieve_candidates(question: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    anchors = extract_anchors(question)
    matchers = build_anchor_matchers(anchors)

    vector = embed_query(question)
    idx = pinecone_index()

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
            text_norm = text.lower()

            # Dedupe by text hash
            h = hash_text(text_norm)
            if h in seen:
                continue
            seen.add(h)

            hits = anchor_hits(text, matchers)

            # Must satisfy at least ONE anchor group
            if anchors and not any(hits.values()):
                continue

            # Reject common "tren" false positives (T-bol/Trenoball)
            if reject_false_tren_hits(text, hits):
                continue

            candidates.append({
                "text": text,
                "score": float(m.get("score") or 0.0),
                "hits": hits,
                "namespace": ns,
                "podcast": first(md, ["podcast", "show", "channel", "series"]),
                "episode": first(md, ["episode", "title", "episode_title", "video_title", "name"]),
                "speaker": first(md, ["speaker", "host", "guest", "author"]),
                "timestamp": first(md, ["timestamp", "time", "start_time", "ts", "start"]),
                "source": first(md, ["source", "file", "path", "url"]),
            })

    # Keep broad pool; selection will handle coverage/quality
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates, anchors


# ==========================
# SELECTION (Coverage-aware)
# ==========================

def select_quotes(candidates: List[Dict[str, Any]],
                  anchors: Dict[str, List[str]],
                  max_quotes: int) -> List[Dict[str, Any]]:
    """
    Greedy set cover:
    - Prefer quotes that add NEW uncovered anchors
    - Tie-break by vector score
    """
    if not candidates:
        return []

    if not anchors:
        # No anchors detected; just return top N
        return candidates[:max_quotes]

    covered = {k: False for k in anchors.keys()}
    selected: List[Dict[str, Any]] = []
    remaining = candidates[:]

    def coverage_gain(c: Dict[str, Any]) -> int:
        gain = 0
        for k in covered:
            if not covered[k] and c["hits"].get(k):
                gain += 1
        return gain

    while remaining and len(selected) < max_quotes:
        # Pick candidate with best (gain, score)
        best_i = -1
        best_key = (-1, -1.0)

        for i, c in enumerate(remaining):
            gain = coverage_gain(c)
            key = (gain, c["score"])
            if key > best_key:
                best_key = key
                best_i = i

        if best_i == -1:
            break

        chosen = remaining.pop(best_i)
        selected.append(chosen)

        # update coverage
        for k in covered:
            if chosen["hits"].get(k):
                covered[k] = True

        # If full intent covered, we can stop early
        if all(covered.values()):
            break

    # If we still have room and want to fill to max_quotes, append best-scoring leftovers
    if len(selected) < max_quotes and remaining:
        selected_ids = {hash_text(s["text"].lower()) for s in selected}
        for c in remaining:
            if len(selected) >= max_quotes:
                break
            if hash_text(c["text"].lower()) in selected_ids:
                continue
            selected.append(c)

    return selected


# ==========================
# OUTPUT
# ==========================

def format_answer(quotes: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("Answer:")

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


# ==========================
# MAIN
# ==========================

def main():
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise RuntimeError("No question provided")

    candidates, anchors = retrieve_candidates(question)
    quotes = select_quotes(candidates, anchors, MAX_QUOTES)

    print(format_answer(quotes))

if __name__ == "__main__":
    main()
