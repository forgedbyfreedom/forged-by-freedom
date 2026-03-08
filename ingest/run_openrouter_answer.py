#!/usr/bin/env python3
"""
Ask Coach Bryan – Retrieval Engine (JSON output)

Returns:
{
  "ok": true,
  "question": "...",
  "anchors": { ... },
  "quotes": [
     {
       "text": "...",
       "podcast": "...",
       "episode": "...",
       "speaker": "...",
       "timestamp": "...",
       "source": "...",
       "namespace": "...",
       "chunk_index": 123,
       "score": 0.78,
       "hits": {"compound": true, "population": false, "risk": true}
     }, ...
  ],
  "coverage": {"population": true, "risk": true},
  "note": "..."   # present only when quotes is empty
}

Never prints "insufficient evidence" itself. That belongs to the server formatter.
"""

from __future__ import annotations

import os
import sys
import re
import json
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import requests
from pinecone import Pinecone

# ==========================
# CONFIG
# ==========================

INDEX_NAME = os.getenv("PINECONE_INDEX", "forged-freedom-ai")
TOP_K_PER_NAMESPACE = int(os.getenv("FBF_TOPK_PER_NAMESPACE", "80"))
MAX_QUOTES = int(os.getenv("FBF_FINAL_QUOTES", "3"))
WINDOW_RADIUS = int(os.getenv("FBF_WINDOW_RADIUS", "2"))

NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "default",
    "transcripts",
    ""
]

OPENROUTER_EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-large")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")

# ==========================
# UTILS
# ==========================

def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

def first(md: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = md.get(k)
        if v is None:
            continue
        t = str(v).strip()
        if t:
            return t
    return ""

def compile_patterns(terms: List[str]) -> List[re.Pattern]:
    pats: List[re.Pattern] = []
    for term in terms:
        term = term.strip().lower()
        if not term:
            continue
        if term.endswith("*"):
            stem = re.escape(term[:-1])
            pats.append(re.compile(rf"\b{stem}\w*\b", re.IGNORECASE))
        else:
            esc = re.escape(term)
            pats.append(re.compile(rf"(?<!\w){esc}(?!\w)", re.IGNORECASE))
    return pats

# ==========================
# EMBEDDING
# ==========================

def embed_query(query: str) -> List[float]:
    api_key = os.environ["OPENROUTER_API_KEY"]
    url = f"{OPENROUTER_BASE_URL}/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    referer = os.getenv("OPENROUTER_SITE_URL") or os.getenv("OPENROUTER_HTTP_REFERER") or os.getenv("HTTP_REFERER")
    title = os.getenv("OPENROUTER_APP_NAME") or os.getenv("OPENROUTER_X_TITLE")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    r = requests.post(url, headers=headers, json={"model": OPENROUTER_EMBED_MODEL, "input": query}, timeout=45)
    r.raise_for_status()
    emb = r.json()["data"][0]["embedding"]
    if not emb:
        raise RuntimeError("OpenRouter embeddings returned empty embedding")
    return emb

# ==========================
# ANCHORS (Mandatory vs Coverage)
# ==========================

def extract_anchors(question: str) -> Dict[str, Dict[str, Any]]:
    q = question.lower()
    anchors: Dict[str, Dict[str, Any]] = {}

    # Mandatory compound if explicitly referenced
    if "tren" in q:
        anchors["compound"] = {"terms": ["trenbolone", "tren"], "required": True}

    # Coverage anchors (may be satisfied across answer set / window)
    if any(w in q for w in ["woman", "women", "female", "girl", "girls"]):
        anchors["population"] = {"terms": ["woman", "women", "female", "girl", "girls"], "required": False}

    if any(w in q for w in ["viril", "virilization", "mascul", "androgen", "risk", "irreversible", "permanent"]):
        anchors["risk"] = {"terms": ["viril*", "mascul*", "androgen*", "voice", "clitoral", "clit", "facial hair", "irreversible", "permanent"], "required": False}

    return anchors

def build_matchers(anchors: Dict[str, Dict[str, Any]]) -> Dict[str, List[re.Pattern]]:
    return {k: compile_patterns(v["terms"]) for k, v in anchors.items()}

def hits(text: str, matchers: Dict[str, List[re.Pattern]]) -> Dict[str, bool]:
    blob = text.lower()
    return {k: any(p.search(blob) for p in pats) for k, pats in matchers.items()}

def reject_false_tren(text: str) -> bool:
    t = text.lower()
    if re.search(r"\btrenoball\b", t):
        return True
    if re.search(r"\bt-?bol\b", t) or re.search(r"\bturinabol\b", t):
        if not re.search(r"\btrenbolone\b", t):
            return True
    return False

# ==========================
# RETRIEVAL + WINDOW EXPANSION
# ==========================

def pinecone_index():
    return Pinecone(api_key=os.environ["PINECONE_API_KEY"]).Index(INDEX_NAME)

def retrieve_primary_chunks(idx, vector, anchors, matchers) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[int, Dict[str, Any]]]]:
    """
    Returns:
    - primary chunks that satisfy mandatory anchors
    - chunk_map[source_key][chunk_index] = {text, md, ns}
    """
    primary: List[Dict[str, Any]] = []
    chunk_map: Dict[str, Dict[int, Dict[str, Any]]] = {}

    for ns in NAMESPACES:
        res = idx.query(vector=vector, top_k=TOP_K_PER_NAMESPACE, include_metadata=True, namespace=ns)
        for m in res.get("matches", []) or []:
            md = m.get("metadata", {}) or {}
            text = first(md, ["text", "chunk", "content", "quote", "passage", "transcript"])
            if not text:
                continue
            text = norm_ws(text)

            source_key = first(md, ["source", "file", "path", "url"])
            chunk_index = md.get("chunk_index")

            # store chunk for later window expansion if we have an index
            if source_key and chunk_index is not None:
                try:
                    ci = int(chunk_index)
                    chunk_map.setdefault(source_key, {})[ci] = {"text": text, "md": md, "namespace": ns, "score": float(m.get("score") or 0.0)}
                except Exception:
                    pass

            h = hits(text, matchers)

            # enforce mandatory anchors per quote
            reject = False
            for k, cfg in anchors.items():
                if cfg["required"] and not h.get(k, False):
                    reject = True
                    break
            if reject:
                continue

            # false tren cleanup (only relevant if compound anchor exists)
            if "compound" in anchors and reject_false_tren(text):
                continue

            if anchors and not any(h.values()):
                continue

            primary.append({
                "text": text,
                "md": md,
                "namespace": ns,
                "score": float(m.get("score") or 0.0),
                "source_key": source_key,
                "chunk_index": int(chunk_index) if isinstance(chunk_index, (int, float, str)) and str(chunk_index).isdigit() else None,
                "hits": h,
            })

    # sort best-first (helps anchor candidates)
    primary.sort(key=lambda x: x["score"], reverse=True)
    return primary, chunk_map

def expand_window(primary: List[Dict[str, Any]], chunk_map: Dict[str, Dict[int, Dict[str, Any]]], matchers) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    seen = set()

    for p in primary:
        # include the primary chunk
        k = sha1(p["text"].lower())
        if k not in seen:
            expanded.append(p)
            seen.add(k)

        sk = p.get("source_key")
        ci = p.get("chunk_index")
        if not sk or ci is None:
            continue

        for i in range(ci - WINDOW_RADIUS, ci + WINDOW_RADIUS + 1):
            if i == ci:
                continue
            neighbor = chunk_map.get(sk, {}).get(i)
            if not neighbor:
                continue
            t = neighbor["text"]
            kk = sha1(t.lower())
            if kk in seen:
                continue
            h = hits(t, matchers)
            expanded.append({
                "text": t,
                "md": neighbor["md"],
                "namespace": neighbor["namespace"],
                "score": neighbor["score"],
                "source_key": sk,
                "chunk_index": i,
                "hits": h,
            })
            seen.add(kk)

    # sort by score (still useful) but selection will handle coverage
    expanded.sort(key=lambda x: x["score"], reverse=True)
    return expanded

# ==========================
# SELECTION (coverage-aware)
# ==========================

def select_quotes(candidates: List[Dict[str, Any]], anchors: Dict[str, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """
    Enforce mandatory anchors already satisfied by construction.
    Now greedily cover non-required anchors across the answer set.
    """
    if not candidates:
        return [], {}

    coverage_targets = {k: False for k, cfg in anchors.items() if not cfg["required"]}
    selected: List[Dict[str, Any]] = []

    def gain(c: Dict[str, Any]) -> int:
        g = 0
        for k in coverage_targets:
            if not coverage_targets[k] and c["hits"].get(k, False):
                g += 1
        return g

    remaining = candidates[:]
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
        for k in coverage_targets:
            if chosen["hits"].get(k, False):
                coverage_targets[k] = True

        if coverage_targets and all(coverage_targets.values()):
            break

    return selected, coverage_targets

# ==========================
# OUTPUT SHAPING
# ==========================

def shape_quote(q: Dict[str, Any]) -> Dict[str, Any]:
    md = q["md"]
    return {
        "text": q["text"],
        "podcast": first(md, ["podcast", "show", "channel", "series"]),
        "episode": first(md, ["episode", "title", "episode_title", "video_title", "name"]),
        "speaker": first(md, ["speaker", "host", "guest", "author"]),
        "timestamp": first(md, ["timestamp", "time", "start_time", "ts", "start"]),
        "source": first(md, ["source", "file", "path", "url"]),
        "namespace": q.get("namespace", ""),
        "chunk_index": q.get("chunk_index"),
        "score": q.get("score", 0.0),
        "hits": q.get("hits", {}),
    }

def main():
    # Accept args or stdin JSON {"question": "..."}
    question = ""
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
    else:
        raw = sys.stdin.read().strip()
        if raw:
            try:
                payload = json.loads(raw)
                question = str(payload.get("question", "")).strip()
            except json.JSONDecodeError:
                question = raw.strip()

    if not question:
        print(json.dumps({"ok": False, "error": "No question provided"}))
        sys.exit(1)

    anchors = extract_anchors(question)
    matchers = build_matchers(anchors)

    vec = embed_query(question)
    idx = pinecone_index()

    primary, chunk_map = retrieve_primary_chunks(idx, vec, anchors, matchers)
    expanded = expand_window(primary, chunk_map, matchers)

    selected, coverage = select_quotes(expanded, anchors)
    shaped = [shape_quote(q) for q in selected]

    out: Dict[str, Any] = {
        "ok": True,
        "question": question,
        "anchors": anchors,
        "quotes": shaped,
        "coverage": coverage
    }

    if not shaped:
        out["note"] = (
            "No verbatim transcript excerpts were found that explicitly satisfy the mandatory parts of this question "
            "(e.g., the named compound). The system does not infer or summarize; it only returns direct spoken quotes."
        )

    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
