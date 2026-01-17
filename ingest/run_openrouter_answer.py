#!/usr/bin/env python3
"""
run_openrouter_answer.py (FULL REPLACEMENT)

Quote-only retrieval system for "Ask Coach Bryan".

Key fixes implemented:
1) Embed the user query (OpenRouter embeddings) BEFORE Pinecone search
2) Query MULTIPLE namespaces (including legacy empty-string namespace "")
3) Merge + dedupe results across namespaces
4) Re-score matches with strong lexical boosts for tren/women/virilization
5) Select top 3 quotes AFTER scoring, not before

Default output: JSON {"answer": "..."} to stdout
"""

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

# Pinecone v3 client
try:
    from pinecone import Pinecone
except Exception as e:
    raise RuntimeError(
        "Missing pinecone client. Install with: pip install pinecone-client"
    ) from e


# ---------------------------
# Config
# ---------------------------

DEFAULT_NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "default",
    "transcripts",
    "",  # legacy unnamed namespace (empty string) - CRITICAL
]

# Retrieval breadth per namespace. Keep reasonably high; rescoring will filter.
TOP_K_PER_NAMESPACE = int(os.getenv("FBF_TOPK_PER_NAMESPACE", "40"))

# Final number of quotes returned
FINAL_QUOTE_COUNT = int(os.getenv("FBF_FINAL_QUOTES", "3"))

# Dedupe behavior
DEDUP_BY_TEXT = True  # set False if you prefer dedupe by id only


# ---------------------------
# Helpers
# ---------------------------

def _env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val or ""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_lower(s: Any) -> str:
    if s is None:
        return ""
    return str(s).lower()


def _compact_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _hash_text(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def _get_first(metadata: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = metadata.get(k)
        if v is None:
            continue
        v = str(v).strip()
        if v:
            return v
    return ""


@dataclass
class Match:
    id: str
    namespace: str
    pinecone_score: float
    rescored: float
    text: str
    podcast: str
    episode: str
    speaker: str
    timestamp: str
    source: str
    raw_metadata: Dict[str, Any]


# ---------------------------
# OpenRouter Embeddings
# ---------------------------

def embed_query_openrouter(query: str) -> List[float]:
    api_key = _env("OPENROUTER_API_KEY", required=True)
    base_url = _env("OPENROUTER_BASE_URL", required=False, default="https://openrouter.ai/api/v1").rstrip("/")
    model = _env("OPENROUTER_EMBED_MODEL", required=False, default="text-embedding-3-large")

    url = f"{base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Optional but recommended by OpenRouter
    referer = os.getenv("OPENROUTER_SITE_URL") or os.getenv("OPENROUTER_HTTP_REFERER") or os.getenv("HTTP_REFERER")
    title = os.getenv("OPENROUTER_APP_NAME") or os.getenv("OPENROUTER_X_TITLE")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    payload = {
        "model": model,
        "input": query,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=45)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter embeddings failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    # OpenAI-compatible shape: {"data":[{"embedding":[...]}], ...}
    emb = data["data"][0]["embedding"]
    if not isinstance(emb, list) or not emb:
        raise RuntimeError("OpenRouter embeddings returned empty embedding")
    return emb


# ---------------------------
# Pinecone Retrieval
# ---------------------------

def pinecone_client() -> Tuple[Any, Any]:
    api_key = _env("PINECONE_API_KEY", required=True)
    index_name = _env("PINECONE_INDEX", required=False, default="forged-freedom-ai")

    pc = Pinecone(api_key=api_key)
    idx = pc.Index(index_name)
    return pc, idx


def query_namespace(idx: Any, vector: List[float], namespace: str, top_k: int) -> List[Dict[str, Any]]:
    # Pinecone query returns: {"matches":[{"id","score","metadata",...}], ...}
    res = idx.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
        namespace=namespace,
    )
    matches = res.get("matches", []) or []
    return matches


# ---------------------------
# Rescoring / Keyword Boosts
# ---------------------------

# Strongly weight the required topic signals
BOOST_GROUPS: List[Tuple[List[str], float]] = [
    (["trenbolone", "tren ", " tren", "tren-"], 0.35),
    (["enanthate tren", "hex", "acetate", "tren ace", "tren a", "tren e", "tren hex"], 0.08),

    (["woman", "women", "female", "girls", "her ", " she ", "hers"], 0.25),

    (["viril", "viriliz", "masculin", "androgenic", "androgenicity"], 0.35),
    (["voice deep", "deep voice", "voice change", "facial hair", "beard", "hair growth"], 0.35),
    (["clitoral", "clit", "clit growth", "clitoral enlargement"], 0.45),
    (["irreversible", "permanent", "won't go back", "doesn't go back", "can't reverse"], 0.45),
    (["acne", "oily skin", "hairline", "bald", "alopecia"], 0.10),
    (["menstrual", "period", "cycle", "amenorrhea"], 0.10),
]

# Optional mild penalties for common “off-topic drift”
PENALTY_GROUPS: List[Tuple[List[str], float]] = [
    (["clomid", "clomiphene", "fertility", "ivf", "sperm", "semen"], 0.08),
    (["anavar only", "var only", "just anavar", "only test"], 0.05),
]


def compute_rescore(base_score: float, question: str, text: str, metadata: Dict[str, Any]) -> float:
    """
    Combine Pinecone similarity with lexical boosts.
    Pinecone score is typically in [0,1] for cosine-ish; we add controlled boosts.
    """
    q = _safe_lower(question)
    t = _safe_lower(text)

    meta_blob = " ".join([
        _safe_lower(metadata.get("podcast")),
        _safe_lower(metadata.get("episode")),
        _safe_lower(metadata.get("speaker")),
        _safe_lower(metadata.get("title")),
        _safe_lower(metadata.get("channel")),
        _safe_lower(metadata.get("source")),
        _safe_lower(metadata.get("file")),
        _safe_lower(metadata.get("path")),
    ])

    blob = f"{t} {meta_blob}"

    score = float(base_score)

    # Prefer content that matches BOTH the question intent and transcript content
    # Add small lift if question has the same key terms
    for terms, weight in BOOST_GROUPS:
        hit_in_blob = any(term in blob for term in terms)
        hit_in_q = any(term in q for term in terms)
        if hit_in_blob and hit_in_q:
            score += weight
        elif hit_in_blob:
            score += weight * 0.65
        elif hit_in_q:
            score += weight * 0.20

    for terms, penalty in PENALTY_GROUPS:
        if any(term in blob for term in terms):
            score -= penalty

    return score


# ---------------------------
# Quote Formatting
# ---------------------------

def extract_fields(md: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    """
    Try multiple common metadata keys from transcript pipelines.
    """
    text = _get_first(md, ["text", "chunk", "content", "quote", "transcript", "passage"])
    podcast = _get_first(md, ["podcast", "show", "channel", "series"])
    episode = _get_first(md, ["episode", "title", "episode_title", "video_title", "name"])
    speaker = _get_first(md, ["speaker", "host", "guest", "author"])
    timestamp = _get_first(md, ["timestamp", "time", "start_time", "ts", "start"])
    source = _get_first(md, ["source", "file", "path", "url"])
    return text, podcast, episode, speaker, timestamp or "", source


def format_answer(quotes: List[Match]) -> str:
    """
    Quote-only output. Minimal connective tissue; no paraphrased summaries.
    """
    lines: List[str] = []
    lines.append("Answer:")
    for i, m in enumerate(quotes, 1):
        q = _compact_ws(m.text)
        # keep it verbatim; just whitespace normalize
        lines.append(f'{i}) "{q}" — {m.speaker or "Unknown Speaker"}, {m.podcast or "Unknown Podcast"}')

    lines.append("")
    lines.append("Sources:")
    for m in quotes:
        q = _compact_ws(m.text)
        lines.append(f"- Podcast: {m.podcast or 'Unknown Podcast'}")
        lines.append(f"  Episode: {m.episode or 'Unknown Episode'}")
        lines.append(f"  Speaker: {m.speaker or 'Unknown Speaker'}")
        if m.timestamp:
            lines.append(f"  Timestamp: {m.timestamp}")
        if m.source:
            lines.append(f"  Source: {m.source}")
        lines.append(f'  Quote: "{q}"')
    return "\n".join(lines)


# ---------------------------
# Main Orchestration
# ---------------------------

def retrieve_quotes(question: str,
                    namespaces: Optional[List[str]] = None,
                    top_k_per_ns: int = TOP_K_PER_NAMESPACE) -> List[Match]:
    namespaces = namespaces or DEFAULT_NAMESPACES

    vector = embed_query_openrouter(question)
    _, idx = pinecone_client()

    all_raw: List[Tuple[str, Dict[str, Any]]] = []  # (namespace, match)
    for ns in namespaces:
        matches = query_namespace(idx, vector=vector, namespace=ns, top_k=top_k_per_ns)
        for m in matches:
            all_raw.append((ns, m))

    # Dedupe
    seen: set = set()
    merged: List[Match] = []

    for ns, m in all_raw:
        mid = str(m.get("id", "")).strip()
        pc_score = float(m.get("score", 0.0) or 0.0)
        md = m.get("metadata", {}) or {}

        text, podcast, episode, speaker, timestamp, source = extract_fields(md)
        text = str(text or "").strip()

        # Skip empty text chunks
        if not text:
            continue

        if DEDUP_BY_TEXT:
            dedupe_key = _hash_text(_compact_ws(text))
        else:
            dedupe_key = mid or _hash_text(_compact_ws(text))

        # If same quote appears in multiple namespaces, keep the best-scoring one
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        resc = compute_rescore(pc_score, question, text, md)

        merged.append(Match(
            id=mid or dedupe_key,
            namespace=ns,
            pinecone_score=pc_score,
            rescored=resc,
            text=text,
            podcast=podcast,
            episode=episode,
            speaker=speaker,
            timestamp=timestamp,
            source=source,
            raw_metadata=md,
        ))

    merged.sort(key=lambda x: x.rescored, reverse=True)
    return merged


def parse_input(argv: List[str]) -> Tuple[str, bool]:
    """
    Supports:
      - python run_openrouter_answer.py "question here"
      - echo '{"question":"..."}' | python run_openrouter_answer.py
    """
    raw = False
    if "--raw" in argv:
        raw = True
        argv = [a for a in argv if a != "--raw"]

    if len(argv) >= 2:
        return " ".join(argv[1:]).strip(), raw

    # stdin JSON
    data = sys.stdin.read().strip()
    if not data:
        raise RuntimeError("No question provided. Pass as arg or via stdin JSON with {\"question\":\"...\"}")
    try:
        payload = json.loads(data)
        q = str(payload.get("question", "")).strip()
        if not q:
            raise RuntimeError("stdin JSON missing 'question'")
        return q, raw
    except json.JSONDecodeError:
        # treat as raw question text
        return data.strip(), raw


def main() -> None:
    question, raw = parse_input(sys.argv)

    # Optional override namespaces via env: comma-separated
    ns_env = os.getenv("FBF_NAMESPACES")
    namespaces = None
    if ns_env:
        namespaces = [n for n in [x.strip() for x in ns_env.split(",")] if n or n == ""]

    results = retrieve_quotes(question, namespaces=namespaces)

    top = results[:FINAL_QUOTE_COUNT]
    answer = format_answer(top) if top else "Answer:\n\nSources:"

    if raw:
        sys.stdout.write(answer)
    else:
        sys.stdout.write(json.dumps({"answer": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
