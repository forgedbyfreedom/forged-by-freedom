#!/usr/bin/env python3
"""
Forged By Freedom - Local Chroma Ingest

Reads corrected transcripts from channels/*/[*.txt] and ingests them into a
local ChromaDB at C:/AI/chroma_db_local. Uses the same chunking strategy as
ingest_to_pinecone.py (tiktoken cl100k_base, 3000-token chunks) but embeds
locally with Ollama (nomic-embed-text, 768-d) instead of OpenAI.

Resumable: skips chunks whose stable id (channel + video_id + chunk_index)
already exists in the target collection.

Usage:
    python ingest_to_chroma.py
    python ingest_to_chroma.py --collection transcripts          # custom collection
    python ingest_to_chroma.py --channel @vigoroussteve           # one channel only
    python ingest_to_chroma.py --limit 5                          # smoke test
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import chromadb
import ollama
import tiktoken

# ============================================================
# CONFIG
# ============================================================
SCRIPT_DIR        = Path(__file__).parent
CHANNELS_DIR      = SCRIPT_DIR / "channels"
CHROMA_DB_PATH    = Path("C:/AI/chroma_db_local")
COLLECTION_NAME   = "forum_content"  # MESO-Rx, Reddit, Janoshik — YouTube transcripts are in topic collections
EMBED_MODEL       = "nomic-embed-text"
EMBED_NUM_CTX     = 8192
CHUNK_TOKENS      = 3000
EMBED_BATCH       = 16
INSERT_BATCH      = 256
MAX_CHARS         = 30000
DISTANCE_METRIC   = "cosine"
TIMESTAMP_FILE    = CHROMA_DB_PATH / "last_ingest.txt"  # tracks mtime cutoff


def _resolve_ollama_host() -> str:
    raw = os.environ.get("OLLAMA_HOST", "").strip()
    if not raw:
        return "http://127.0.0.1:11434"
    h = raw if raw.startswith("http") else f"http://{raw}"
    return h.replace("//0.0.0.0", "//127.0.0.1").replace("//localhost", "//127.0.0.1")


OLLAMA_HOST   = _resolve_ollama_host()
ollama_client = ollama.Client(host=OLLAMA_HOST)
tokenizer     = tiktoken.get_encoding("cl100k_base")
# ============================================================


# ---------- Text + metadata helpers ----------

def chunk_text(text: str):
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), CHUNK_TOKENS):
        yield tokenizer.decode(tokens[i:i + CHUNK_TOKENS])


def extract_channel(path: Path) -> str:
    for part in path.parts:
        if part.startswith("@"):
            return part
    return "unknown"


def extract_video_id(filename: str) -> str:
    m = re.search(r"\[([a-zA-Z0-9_-]{11})\]", filename)
    return m.group(1) if m else ""


def extract_title(filename: str) -> str:
    name = filename.replace(".txt", "")
    name = re.sub(r"\s*\[[a-zA-Z0-9_-]{11}\]$", "", name)
    return name.strip()


def stable_id(channel: str, video_id: str, chunk_index: int, fallback_path: str) -> str:
    # Include a short path hash so .txt and .en.txt for the same video_id get distinct IDs
    path_hash = hashlib.sha1(fallback_path.encode("utf-8")).hexdigest()[:8]
    if channel != "unknown" and video_id:
        return f"{channel}|{video_id}|{path_hash}|{chunk_index}"
    return f"hash|{path_hash}|{chunk_index}"


# ---------- Embedding (mirrors import_to_chroma_local.py) ----------

_ZERO_VECTOR_COUNT = 0


def _normalize_text(t) -> str:
    if t is None:
        return "(empty)"
    s = t if isinstance(t, str) else str(t)
    s = s.strip()
    if not s:
        return "(empty)"
    if len(s) > MAX_CHARS:
        s = s[:MAX_CHARS]
    return s


def embed_one(text: str, dim: int = 768) -> list[float]:
    global _ZERO_VECTOR_COUNT
    safe = _normalize_text(text)
    last_err = None
    for cap in (len(safe), MAX_CHARS // 2, MAX_CHARS // 4, MAX_CHARS // 8, 1500, 500):
        try:
            resp = ollama_client.embed(
                model=EMBED_MODEL,
                input=[safe[:cap]],
                options={"num_ctx": EMBED_NUM_CTX},
            )
            embs = resp.get("embeddings") or ([resp.get("embedding")] if resp.get("embedding") else None)
            if embs and embs[0]:
                return embs[0]
        except Exception as e:
            last_err = e
    _ZERO_VECTOR_COUNT += 1
    print(f"  WARN: zero-vector fallback (#{_ZERO_VECTOR_COUNT}). last_err={str(last_err)[:120]}")
    return [0.0] * dim


def embed_batch(texts: list) -> list[list[float]]:
    if not texts:
        return []
    safe = [_normalize_text(t) for t in texts]
    try:
        resp = ollama_client.embed(
            model=EMBED_MODEL,
            input=safe,
            options={"num_ctx": EMBED_NUM_CTX},
        )
        embs = resp.get("embeddings")
        if embs and len(embs) == len(safe) and all(e is not None for e in embs):
            return embs
    except Exception:
        pass
    return [embed_one(t) for t in safe]


# ---------- Main ingest ----------

FORUM_CHANNELS = {
    "@MesoRx_vendors", "@Janoshik",
    "@Reddit_steroids", "@Reddit_peptides", "@Reddit_sarmssourcetalk",
    "@Reddit_anabolics", "@Reddit_retatrutide", "@Reddit_GLP1",
    "@Reddit_GLP", "@Reddit_fitness", "@Reddit_weightloss", "@Reddit_roids",
}


def iter_transcripts(channel_filter: str | None, since_mtime: float = 0.0):
    """Yield .txt files from forum/scraper channels only (MESO-Rx, Reddit, Janoshik).
    YouTube transcripts are already in the topic-based collections from Pinecone migration.
    If since_mtime > 0, only yield files modified after that timestamp."""
    if not CHANNELS_DIR.exists():
        return
    for txt in sorted(CHANNELS_DIR.rglob("*.txt")):
        if txt.name.startswith("master_"):
            continue
        if channel_filter:
            if channel_filter not in txt.parts:
                continue
        else:
            # Without an explicit --channel filter, only process forum channels
            channel = next((p for p in txt.parts if p.startswith("@")), None)
            if channel not in FORUM_CHANNELS:
                continue
        try:
            st = txt.stat()
            if st.st_size == 0:
                continue
            if since_mtime and st.st_mtime <= since_mtime:
                continue
        except OSError:
            continue
        yield txt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default=COLLECTION_NAME, help="Target Chroma collection")
    parser.add_argument("--channel", default=None, help="Restrict to a single @channel")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N transcript files (smoke test)")
    parser.add_argument("--reembed", action="store_true", help="Force re-ingest even if id already exists")
    parser.add_argument("--since-days", type=float, default=0,
                        help="Only process files modified in the last N days (0=all)")
    args = parser.parse_args()

    # Sanity check Ollama
    try:
        probe = ollama_client.embed(model=EMBED_MODEL, input=["ping"], options={"num_ctx": EMBED_NUM_CTX})
        dim = len(probe["embeddings"][0])
        print(f"Ollama OK | host={OLLAMA_HOST} | model={EMBED_MODEL} | dim={dim}")
    except Exception as e:
        print(f"ERROR: Ollama not reachable: {e}")
        print(f"  Make sure Ollama daemon is running, then: ollama pull {EMBED_MODEL}")
        sys.exit(1)

    CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    collection = client.get_or_create_collection(
        name=args.collection,
        metadata={"hnsw:space": DISTANCE_METRIC, "embed_model": EMBED_MODEL},
    )
    print(f"Collection: {args.collection} | existing count: {collection.count():,}")

    # Buffers
    pending_ids: list[str] = []
    pending_metas: list[dict] = []
    pending_docs: list[str] = []

    insert_buf_ids: list[str] = []
    insert_buf_embs: list[list[float]] = []
    insert_buf_metas: list[dict] = []
    insert_buf_docs: list[str] = []

    files_seen = files_kept = chunks_total = chunks_skipped = 0

    def flush_embeddings():
        nonlocal pending_ids, pending_metas, pending_docs
        if not pending_ids:
            return
        embs = embed_batch(pending_docs)
        insert_buf_ids.extend(pending_ids)
        insert_buf_embs.extend(embs)
        insert_buf_metas.extend(pending_metas)
        insert_buf_docs.extend(pending_docs)
        pending_ids = []
        pending_metas = []
        pending_docs = []

    def flush_insert():
        nonlocal chunks_total
        if not insert_buf_ids:
            return
        # Dedup within batch (guards against any edge-case duplicate paths)
        seen: set = set()
        deduped = [(i, e, m, d) for i, e, m, d in zip(insert_buf_ids, insert_buf_embs, insert_buf_metas, insert_buf_docs) if i not in seen and not seen.add(i)]
        ids_u, embs_u, metas_u, docs_u = zip(*deduped) if deduped else ([], [], [], [])
        collection.upsert(
            ids=list(ids_u),
            embeddings=list(embs_u),
            metadatas=list(metas_u),
            documents=list(docs_u),
        )
        chunks_total += len(insert_buf_ids)
        print(f"  upserted {chunks_total:,} so far ({_ZERO_VECTOR_COUNT} zero-vec)")
        insert_buf_ids.clear()
        insert_buf_embs.clear()
        insert_buf_metas.clear()
        insert_buf_docs.clear()

    # Determine mtime cutoff — avoid the O(N²) Chroma ID scan entirely.
    # Nightly runs only need to process files written since the last ingest.
    # Full scans (--reembed or --since-days 0 with no timestamp file) still work.
    since_mtime = 0.0
    if not args.reembed and not args.channel and args.since_days == 0:
        if TIMESTAMP_FILE.exists():
            try:
                since_mtime = float(TIMESTAMP_FILE.read_text().strip())
                from datetime import datetime
                dt = datetime.fromtimestamp(since_mtime).strftime("%Y-%m-%d %H:%M")
                print(f"Incremental mode: only files newer than {dt}")
            except Exception:
                since_mtime = 0.0
    elif args.since_days > 0:
        import time
        since_mtime = time.time() - args.since_days * 86400
        from datetime import datetime
        dt = datetime.fromtimestamp(since_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"Incremental mode: only files newer than {dt} (--since-days {args.since_days})")

    if since_mtime == 0.0 and not args.reembed:
        print("Full scan mode (no timestamp file found — first run or --reembed)")

    # Record run start time before processing (written on success at the end)
    import time as _time
    run_start = _time.time()

    for txt_path in iter_transcripts(args.channel, since_mtime=since_mtime):
        if args.limit and files_kept >= args.limit:
            break
        files_seen += 1

        try:
            text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception as e:
            print(f"  skip (read error): {txt_path.name}: {e}")
            continue
        if not text:
            continue

        channel = extract_channel(txt_path)
        video_id = extract_video_id(txt_path.name)
        title = extract_title(txt_path.name)
        rel_source = str(txt_path.relative_to(CHANNELS_DIR.parent)).replace("\\", "/")

        chunks = list(chunk_text(text))
        total_chunks = len(chunks)
        if total_chunks == 0:
            continue
        files_kept += 1

        for chunk_index, chunk in enumerate(chunks):
            cid = stable_id(channel, video_id, chunk_index, rel_source)

            meta = {
                "channel": channel,
                "title": title,
                "video_id": video_id,
                "source": rel_source,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "word_count": len(chunk.split()),
            }

            pending_ids.append(cid)
            pending_metas.append(meta)
            pending_docs.append(chunk)

            if len(pending_ids) >= EMBED_BATCH:
                flush_embeddings()
            if len(insert_buf_ids) >= INSERT_BATCH:
                flush_insert()

    flush_embeddings()
    flush_insert()

    # Save run-start timestamp so next incremental run only sees new files
    if not args.channel and not args.limit:
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        TIMESTAMP_FILE.write_text(str(run_start))

    print()
    print("=" * 60)
    print(f"Files seen   : {files_seen:,}")
    print(f"Files ingested: {files_kept:,}")
    print(f"Chunks added : {chunks_total:,}")
    print(f"Chunks skipped (already in DB): {chunks_skipped:,}")
    print(f"Zero-vector fallbacks: {_ZERO_VECTOR_COUNT}")
    print(f"DB at: {CHROMA_DB_PATH.absolute()} | collection={args.collection} | total={collection.count():,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
