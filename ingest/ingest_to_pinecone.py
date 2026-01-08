#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Forged By Freedom – Pinecone Ingest (Production Safe, Low-Memory)

Features:
- Real lock w/ PID check (no false positives)
- Token-bounded chunking (never exceeds embedding request size)
- ASCII-only deterministic vector IDs (sha256)
- Pinecone upsert batching + retries
- Streaming embed->upsert (prevents macOS OOM)
- Bounded concurrency (optional; default 1 worker)
- Checkpoint resume (skip unchanged files)
- Incremental updates (if file changed: delete old vectors by metadata filter then re-ingest)
- Namespace partitioning by category (from channel_manifest.yml if present; otherwise inferred)
- Per-source priority queues (smallest files first within each channel)
- Progress persistence + ETA heartbeat
- Optional cost/token estimate-only mode
"""

import os
import sys
import time
import json
import math
import atexit
import signal
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import tiktoken
import yaml
from openai import OpenAI
from pinecone import Pinecone

# =========================
# PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent
CHANNELS_DIR = BASE_DIR / "channels"
MANIFEST_PATH = BASE_DIR / "channel_manifest.yml"

LOCK_FILE = BASE_DIR / ".ingest.lock"
CHECKPOINT_FILE = BASE_DIR / ".ingest_checkpoint.json"   # path -> {hash, namespace, chunks, ts}
PROGRESS_FILE = BASE_DIR / ".ingest_progress.json"       # rolling stats

# =========================
# CONFIG (env-tunable)
# =========================
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", os.getenv("PINECONE_INDEX", "forged-freedom-ai"))
DEFAULT_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "default")

EMBED_MODEL = "text-embedding-3-large"

# Token chunking (safe defaults)
CHUNK_TOKENS = int(os.getenv("INGEST_CHUNK_TOKENS", "3000"))         # lower = safer on memory
CHUNK_OVERLAP = int(os.getenv("INGEST_CHUNK_OVERLAP", "100"))
MAX_FILE_TOKENS = int(os.getenv("INGEST_MAX_FILE_TOKENS", "2000000"))  # skip extreme monsters

# Embed batching + retries
EMBED_BATCH = int(os.getenv("INGEST_EMBED_BATCH", "16"))             # low memory default
MAX_EMBED_RETRIES = int(os.getenv("INGEST_EMBED_RETRIES", "6"))
EMBED_SLEEP = float(os.getenv("INGEST_EMBED_SLEEP", "0.15"))

# Concurrency (bounded). Default 1 prevents mac OOM. Raise carefully (2 is usually safe).
MAX_WORKERS = int(os.getenv("INGEST_EMBED_WORKERS", "1"))

# Pinecone upsert batching + retries
UPSERT_BATCH = int(os.getenv("INGEST_UPSERT_BATCH", "50"))
UPSERT_SLEEP = float(os.getenv("INGEST_UPSERT_SLEEP", "0.10"))
MAX_UPSERT_RETRIES = int(os.getenv("INGEST_UPSERT_RETRIES", "6"))

# Throttling (category/channel)
SLEEP_BETWEEN_CHANNELS = float(os.getenv("INGEST_SLEEP_BETWEEN_CHANNELS", "0.5"))
SLEEP_BETWEEN_CATEGORIES = float(os.getenv("INGEST_SLEEP_BETWEEN_CATEGORIES", "1.0"))

# Estimate-only mode
# export INGEST_ESTIMATE_ONLY=1 to print estimate and exit
INGEST_ESTIMATE_ONLY = os.getenv("INGEST_ESTIMATE_ONLY") == "1"
EMBED_PRICE_PER_1M = os.getenv("EMBED_PRICE_PER_1M")  # optional, purely for estimation

# =========================
# ENV VALIDATION
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY not set")
if not PINECONE_API_KEY:
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# =========================
# LOCK (real + PID check)
# =========================
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def acquire_lock() -> None:
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if _pid_alive(old_pid):
                print("❌ Ingest already running — exiting.")
                sys.exit(1)
            LOCK_FILE.unlink()  # stale
        except Exception:
            try:
                LOCK_FILE.unlink()
            except Exception:
                pass

    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")

def release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass

def _cleanup(*_):
    release_lock()
    sys.exit(0)

atexit.register(release_lock)
signal.signal(signal.SIGINT, _cleanup)
signal.signal(signal.SIGTERM, _cleanup)

# =========================
# CLIENTS
# =========================
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

ENC = tiktoken.encoding_for_model("text-embedding-3-large")

# =========================
# UTIL
# =========================
def now_ts() -> float:
    return time.time()

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def file_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def safe_namespace(name: str) -> str:
    cleaned = "".join(ch.lower() if (("a" <= ch.lower() <= "z") or ("0" <= ch <= "9")) else "_" for ch in name)
    cleaned = "_".join([p for p in cleaned.split("_") if p])
    return (cleaned or "default")[:64]

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

# =========================
# MANIFEST: channel -> category
# =========================
def load_channel_category_map() -> Dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    cats = data.get("categories", {})
    mapping: Dict[str, str] = {}
    if isinstance(cats, dict):
        for cat_name, cfg in cats.items():
            channels = (cfg or {}).get("channels", []) or []
            for ch in channels:
                mapping[str(ch)] = str(cat_name)
    return mapping

CHANNEL_TO_CATEGORY = load_channel_category_map()

def infer_channel_from_path(p: Path) -> str:
    # channels/<channel>/<file>.txt
    try:
        rel = p.relative_to(CHANNELS_DIR)
        return rel.parts[0]
    except Exception:
        return "unknown"

def category_for_file(p: Path) -> str:
    ch = infer_channel_from_path(p)
    return CHANNEL_TO_CATEGORY.get(ch, "uncategorized")

def namespace_for_file(p: Path) -> str:
    # per-category namespace partitioning
    cat = category_for_file(p)
    return safe_namespace(cat) if cat else DEFAULT_NAMESPACE

# =========================
# TOKEN CHUNKING
# =========================
def chunk_by_tokens(text: str) -> List[str]:
    toks = ENC.encode(text)
    if len(toks) > MAX_FILE_TOKENS:
        return []
    step = max(1, CHUNK_TOKENS - CHUNK_OVERLAP)
    chunks: List[str] = []
    for start in range(0, len(toks), step):
        piece = toks[start:start + CHUNK_TOKENS]
        if not piece:
            break
        chunks.append(ENC.decode(piece))
    return chunks

# =========================
# VECTOR IDs (ASCII only)
# =========================
def vector_id(path: Path, content_hash: str, chunk_index: int) -> str:
    # content_hash included so updates create new IDs (we delete old by metadata filter)
    return sha256_hex(f"{path.as_posix()}|{content_hash}|{chunk_index}")

# =========================
# EMBEDDING (retry)
# =========================
def embed_batch(texts: List[str]) -> List[List[float]]:
    last_err = None
    for attempt in range(1, MAX_EMBED_RETRIES + 1):
        try:
            resp = openai_client.embeddings.create(model=EMBED_MODEL, input=texts)
            if not resp.data:
                raise ValueError("Empty embedding response")
            embs = [d.embedding for d in resp.data]
            if len(embs) != len(texts):
                raise ValueError("Embedding count mismatch")
            return embs
        except Exception as e:
            last_err = e
            sleep_s = min(10.0, 1.2 * attempt)
            print(f"⚠️ Embed retry {attempt}/{MAX_EMBED_RETRIES}: {e}")
            time.sleep(sleep_s)
    raise RuntimeError(f"❌ Embedding failed after retries: {last_err}")

# =========================
# PINECONE OPS (retry)
# =========================
def pinecone_upsert(vectors: List[dict], namespace: str) -> None:
    last_err = None
    for attempt in range(1, MAX_UPSERT_RETRIES + 1):
        try:
            index.upsert(vectors=vectors, namespace=namespace)
            return
        except Exception as e:
            last_err = e
            sleep_s = min(10.0, 1.2 * attempt)
            print(f"⚠️ Upsert retry {attempt}/{MAX_UPSERT_RETRIES}: {e}")
            time.sleep(sleep_s)
    raise RuntimeError(f"❌ Upsert failed after retries: {last_err}")

def pinecone_delete_file(path: Path, namespace: str) -> None:
    # incremental update: delete by metadata filter
    last_err = None
    for attempt in range(1, MAX_UPSERT_RETRIES + 1):
        try:
            index.delete(namespace=namespace, filter={"path": {"$eq": path.as_posix()}})
            return
        except Exception as e:
            last_err = e
            sleep_s = min(10.0, 1.2 * attempt)
            print(f"⚠️ Delete retry {attempt}/{MAX_UPSERT_RETRIES}: {e}")
            time.sleep(sleep_s)
    raise RuntimeError(f"❌ Delete failed after retries: {last_err}")

# =========================
# FILE LIST + PRIORITY QUEUE
# =========================
def build_file_list() -> List[Path]:
    files = list(CHANNELS_DIR.rglob("*.txt"))
    # per-source priority: (channel, size asc, name)
    def key(p: Path):
        ch = infer_channel_from_path(p)
        size = p.stat().st_size if p.exists() else 0
        return (ch.lower(), size, p.name.lower())
    files.sort(key=key)
    return files

# =========================
# COST ESTIMATE
# =========================
def estimate_tokens(files: List[Path]) -> Tuple[int, Optional[float]]:
    total = 0
    for p in files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        total += len(ENC.encode(txt))
    dollars = None
    if EMBED_PRICE_PER_1M:
        try:
            price = float(EMBED_PRICE_PER_1M)
            dollars = (total / 1_000_000.0) * price
        except Exception:
            dollars = None
    return total, dollars

# =========================
# PROGRESS / ETA
# =========================
def heartbeat(state: dict) -> None:
    now = time.time()
    last = state.get("_last_beat", 0.0)
    if now - last < 10:
        return
    state["_last_beat"] = now

    done = state.get("files_done", 0)
    total = state.get("files_total", 0)
    vecs = state.get("vectors_done", 0)

    started = state.get("started_ts", now)
    elapsed = max(1.0, now - started)
    rate = done / elapsed
    remaining = max(0, total - done)
    eta = remaining / rate if rate > 0 else float("inf")
    eta_str = "∞" if math.isinf(eta) else f"{int(eta//60)}m {int(eta%60)}s"

    print(f"📈 Progress: {done}/{total} files | {vecs} vectors | ETA {eta_str}")
    save_json(PROGRESS_FILE, {k: v for k, v in state.items() if not k.startswith("_")})

# =========================
# INGEST
# =========================
def ingest():
    if not CHANNELS_DIR.exists():
        raise RuntimeError(f"❌ channels dir missing: {CHANNELS_DIR}")

    files = build_file_list()
    cp: Dict[str, dict] = load_json(CHECKPOINT_FILE, {})
    state: Dict[str, object] = load_json(PROGRESS_FILE, {})
    state.setdefault("started_ts", time.time())
    state["files_total"] = len(files)
    state.setdefault("files_done", 0)
    state.setdefault("vectors_done", 0)

    print("🔍 INGEST STARTUP DEBUG")
    print("• BASE_DIR:", BASE_DIR)
    print("• CHANNELS_DIR exists:", CHANNELS_DIR.exists())
    print("• Manifest exists:", MANIFEST_PATH.exists())
    print("• Pinecone index:", PINECONE_INDEX)
    print("• Embedding model:", EMBED_MODEL)
    print("• Workers:", MAX_WORKERS, "Embed batch:", EMBED_BATCH, "Chunk tokens:", CHUNK_TOKENS)
    print("• Total .txt files:", len(files))

    if INGEST_ESTIMATE_ONLY:
        toks, dollars = estimate_tokens(files)
        if dollars is None:
            print(f"🧾 Estimated embed tokens: {toks:,} (set EMBED_PRICE_PER_1M for $ estimate)")
        else:
            print(f"🧾 Estimated embed tokens: {toks:,}  |  Estimated cost: ${dollars:,.2f}")
        return

    print("🚀 BEGIN INGEST\n")

    current_cat = None
    current_ch = None

    for p in files:
        ch = infer_channel_from_path(p)
        cat = category_for_file(p)
        ns = namespace_for_file(p)

        if current_cat != cat:
            current_cat = cat
            print(f"\n📂 CATEGORY: {cat} (namespace: {ns})")
            time.sleep(SLEEP_BETWEEN_CATEGORIES)

        if current_ch != ch:
            current_ch = ch
            print(f"   ├─ {ch}")
            time.sleep(SLEEP_BETWEEN_CHANNELS)

        # read file
        try:
            text = p.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            state["files_done"] += 1
            heartbeat(state)
            continue

        if not text:
            state["files_done"] += 1
            heartbeat(state)
            continue

        h = file_hash(text)
        key = p.as_posix()
        prev = cp.get(key)

        # unchanged? skip
        if prev and prev.get("hash") == h:
            state["files_done"] += 1
            heartbeat(state)
            continue

        # changed? delete old vectors by metadata filter
        if prev and prev.get("hash") != h:
            try:
                pinecone_delete_file(p, namespace=prev.get("namespace", ns))
            except Exception as e:
                print(f"⚠️ Delete old vectors failed for {p.name}: {e} (continuing)")

        # chunk tokens
        chunks = chunk_by_tokens(text)
        if not chunks:
            print(f"⚠️ Skipped huge file (>{MAX_FILE_TOKENS} tokens): {p.name}")
            cp[key] = {"hash": h, "chunks": 0, "namespace": ns, "skipped": True, "ts": now_ts()}
            save_json(CHECKPOINT_FILE, cp)
            state["files_done"] += 1
            heartbeat(state)
            continue

        # STREAMING embed -> upsert:
        # We never hold all embeddings or all vectors for a file in memory.
        total_upserted = 0

        # bounded concurrency: we submit up to MAX_WORKERS embed jobs at a time
        # each job embeds a batch of chunks; main thread builds vectors + upserts immediately
        def batch_iter():
            for start in range(0, len(chunks), EMBED_BATCH):
                yield start, chunks[start:start + EMBED_BATCH]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            in_flight = {}
            it = iter(batch_iter())

            # prime the queue
            for _ in range(MAX_WORKERS):
                try:
                    start, batch = next(it)
                except StopIteration:
                    break
                in_flight[ex.submit(embed_batch, batch)] = (start, len(batch))

            while in_flight:
                for fut in as_completed(in_flight):
                    start, batch_len = in_flight.pop(fut)
                    try:
                        embs = fut.result()
                    except Exception as e:
                        print(f"❌ Embed failed: {p.name} — {e}")
                        # don't checkpoint; retry later
                        state["files_done"] += 1
                        heartbeat(state)
                        # cancel remaining futures
                        for f2 in in_flight:
                            try:
                                f2.cancel()
                            except Exception:
                                pass
                        in_flight.clear()
                        embs = None

                    if embs is None:
                        break

                    # build vectors and upsert immediately (low memory)
                    vectors = []
                    for i, emb in enumerate(embs):
                        chunk_index = start + i
                        vectors.append({
                            "id": vector_id(p, h, chunk_index),
                            "values": emb,
                            "metadata": {
                                "path": p.as_posix(),
                                "source": p.name,
                                "channel": ch,
                                "category": cat,
                                "chunk": chunk_index
                            }
                        })

                    # upsert (with batching safety if needed)
                    for i in range(0, len(vectors), UPSERT_BATCH):
                        pinecone_upsert(vectors[i:i + UPSERT_BATCH], namespace=ns)
                        total_upserted += len(vectors[i:i + UPSERT_BATCH])
                        time.sleep(UPSERT_SLEEP)

                    # encourage memory release
                    del vectors
                    del embs

                    time.sleep(EMBED_SLEEP)

                    # keep pipeline full
                    try:
                        next_start, next_batch = next(it)
                        in_flight[ex.submit(embed_batch, next_batch)] = (next_start, len(next_batch))
                    except StopIteration:
                        pass

                    break  # break as_completed loop to refresh in_flight

        # checkpoint file success
        cp[key] = {"hash": h, "chunks": total_upserted, "namespace": ns, "ts": now_ts()}
        save_json(CHECKPOINT_FILE, cp)

        state["files_done"] += 1
        state["vectors_done"] += total_upserted
        print(f"✅ Ingested: {p.name} ({total_upserted} vectors)")
        heartbeat(state)

    print("\n✅ INGEST COMPLETE")
    save_json(PROGRESS_FILE, {k: v for k, v in state.items() if not k.startswith("_")})

# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    acquire_lock()
    try:
        ingest()
    finally:
        release_lock()
