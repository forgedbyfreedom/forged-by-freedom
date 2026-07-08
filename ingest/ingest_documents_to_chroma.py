#!/usr/bin/env python3
"""
Forged By Freedom — Local Chroma Ingest for DOCUMENTS
(PDF / EPUB / DOCX / TXT / MD / JPG/PNG-with-OCR)

Companion to ingest_to_chroma.py. That script ingests forum/YouTube
transcripts organized as `channels/@ChannelName/*.txt`. This script
ingests standalone documents — books, PDFs, program guides,
bloodwork PDFs, supplier COAs — organized as arbitrary folder trees
you point it at.

Same chunking / embedding / DB conventions:
    - tiktoken cl100k_base, 3000-token chunks (matches ingest_to_pinecone.py
      and ingest_to_chroma.py, so retrieval is uniform)
    - Ollama nomic-embed-text (768-d) via the same host as ingest_to_chroma.py
    - ChromaDB at C:/AI/chroma_db_local (same store, different collections)
    - Cosine distance
    - Resumable: stable ID per (source_path, chunk_index); reruns skip
      chunks already present in the target collection.

Default collection routing (auto-picked from top-level folder name;
override with --collection):

    Personal / medical:
        precision_bloodwork*.pdf                    → personal_medical
        *bloodwork*, *lab*, *coa*, *panel*.*        → personal_medical
        *zhuoyue*, supplier COA jpg/png             → personal_medical
    Reference / training / anabolics:
        everything else                             → bodybuilding_reference

Content-type notes:
    - PDF text extraction: PyMuPDF (pip install pymupdf) — falls back to
      pdfplumber if PyMuPDF is unavailable.
    - EPUB: ebooklib + BeautifulSoup.
    - DOCX: python-docx.
    - TXT / MD: read directly.
    - JPG / PNG: OCR via pytesseract (needs Tesseract installed:
      `winget install UB-Mannheim.TesseractOCR` on Windows).
    - .torrent: SKIPPED with a warning — those are metadata, not content.

Usage (from the repo root, on the Windows PC where Ollama runs):

    python ingest/ingest_documents_to_chroma.py \\
        --input "C:\\Users\\Antonelli\\Downloads" \\
        --dry-run

    # once dry-run output looks right:
    python ingest/ingest_documents_to_chroma.py \\
        --input "C:\\Users\\Antonelli\\Downloads"

    # or force a single collection:
    python ingest/ingest_documents_to_chroma.py \\
        --input "C:\\Users\\Antonelli\\Downloads\\Bodybuilding e-Books" \\
        --collection bodybuilding_reference

    # respect a manifest of paths to skip (one per line, glob supported):
    python ingest/ingest_documents_to_chroma.py \\
        --input "C:\\Users\\Antonelli\\Downloads" \\
        --skip-manifest ingest/skip_paths.txt
"""

import argparse
import fnmatch
import hashlib
import os
import re
import sys
from pathlib import Path

import chromadb
import ollama
import tiktoken

# ============================================================
# CONFIG (mirrors ingest_to_chroma.py where relevant)
# ============================================================
SCRIPT_DIR             = Path(__file__).parent
CHROMA_DB_PATH         = Path("C:/AI/chroma_db_local")
DEFAULT_COLLECTION     = "bodybuilding_reference"
PERSONAL_COLLECTION    = "personal_medical"
EMBED_MODEL            = "nomic-embed-text"
EMBED_NUM_CTX          = 8192
CHUNK_TOKENS           = 3000
EMBED_BATCH            = 16
INSERT_BATCH           = 256
MAX_CHARS              = 30000
DISTANCE_METRIC        = "cosine"

# File-type routing
TEXT_LIKE_EXTS   = {".txt", ".md", ".markdown"}
PDF_EXTS         = {".pdf"}
EPUB_EXTS        = {".epub"}
DOCX_EXTS        = {".docx"}
IMAGE_EXTS       = {".jpg", ".jpeg", ".png", ".webp"}
SKIP_EXTS        = {".torrent", ".exe", ".zip", ".rar", ".7z", ".iso",
                    ".mp4", ".mkv", ".avi", ".mov", ".mp3", ".wav", ".flac",
                    ".m4a", ".m4b"}
SUPPORTED_EXTS   = TEXT_LIKE_EXTS | PDF_EXTS | EPUB_EXTS | DOCX_EXTS | IMAGE_EXTS

# Personal-collection routing patterns (case-insensitive; match against filename)
PERSONAL_PATTERNS = [
    "*bloodwork*", "*blood_work*", "*labs*", "*lab_panel*", "*panel*",
    "*coa*", "*certificate_of_analysis*", "*zhuoyue*",
    "*hormone*panel*", "*testosterone*panel*", "precision*",
]


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


# ---------- Extractors (lazy-imported so a missing lib doesn't kill the whole script) ----------

def _extract_pdf(path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # fall back to pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                return "\n\n".join((p.extract_text() or "") for p in pdf.pages)
        except ImportError:
            raise RuntimeError(
                "PDF extraction requires PyMuPDF (pip install pymupdf) or "
                "pdfplumber (pip install pdfplumber)."
            )
    doc = fitz.open(str(path))
    try:
        return "\n\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def _extract_epub(path: Path) -> str:
    try:
        from ebooklib import epub, ITEM_DOCUMENT
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError(
            "EPUB extraction requires ebooklib + beautifulsoup4 "
            "(pip install EbookLib beautifulsoup4)."
        )
    book = epub.read_epub(str(path))
    parts = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _extract_docx(path: Path) -> str:
    try:
        import docx
    except ImportError:
        raise RuntimeError(
            "DOCX extraction requires python-docx (pip install python-docx)."
        )
    doc = docx.Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_image_ocr(path: Path) -> str:
    """OCR via Tesseract. Only run on files whose name suggests a lab/COA.
    General product photos and screenshots aren't useful text sources."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "Image OCR requires pytesseract + Pillow (pip install pytesseract Pillow). "
            "The Tesseract binary must be installed separately: "
            "`winget install UB-Mannheim.TesseractOCR` on Windows."
        )
    return pytesseract.image_to_string(Image.open(str(path)))


def _extract_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode("utf-8", errors="replace")


def extract(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in PDF_EXTS:
        return _extract_pdf(path)
    if ext in EPUB_EXTS:
        return _extract_epub(path)
    if ext in DOCX_EXTS:
        return _extract_docx(path)
    if ext in IMAGE_EXTS:
        return _extract_image_ocr(path)
    if ext in TEXT_LIKE_EXTS:
        return _extract_text(path)
    raise ValueError(f"unsupported extension: {ext}")


# ---------- Text + chunking (matches ingest_to_chroma.py) ----------

def chunk_text(text: str):
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), CHUNK_TOKENS):
        yield tokenizer.decode(tokens[i:i + CHUNK_TOKENS])


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


def stable_id(source_path: str, chunk_index: int) -> str:
    """Deterministic ID per (path, chunk). Reruns skip existing chunks."""
    h = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:16]
    return f"doc|{h}|{chunk_index}"


# ---------- Embedding (mirrors ingest_to_chroma.py) ----------

_ZERO_VECTOR_COUNT = 0


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


# ---------- Collection routing ----------

def route_collection(path: Path, override: str | None) -> str:
    if override:
        return override
    name_lower = path.name.lower()
    for pat in PERSONAL_PATTERNS:
        if fnmatch.fnmatch(name_lower, pat):
            return PERSONAL_COLLECTION
    # Any file inside a folder whose name matches a personal pattern also routes personal
    for parent in path.parents:
        parent_lower = parent.name.lower()
        for pat in PERSONAL_PATTERNS:
            if fnmatch.fnmatch(parent_lower, pat):
                return PERSONAL_COLLECTION
    return DEFAULT_COLLECTION


# ---------- Walker ----------

def load_skip_manifest(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            lines.append(s)
    return lines


def _should_skip(path: Path, skip_patterns: list[str]) -> bool:
    p_str = str(path).replace("\\", "/").lower()
    for pat in skip_patterns:
        pat_norm = pat.replace("\\", "/").lower()
        # Support both substring and glob
        if pat_norm in p_str:
            return True
        if fnmatch.fnmatch(p_str, f"*{pat_norm}*"):
            return True
    return False


def iter_documents(root: Path, skip_patterns: list[str],
                   include_ocr: bool):
    """Walk root and yield (path, ext) tuples for supported files."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in SKIP_EXTS:
            continue
        if ext not in SUPPORTED_EXTS:
            continue
        if ext in IMAGE_EXTS and not include_ocr:
            # Only OCR images whose filename matches lab/COA patterns unless
            # --ocr-all was passed
            name_lower = path.name.lower()
            if not any(fnmatch.fnmatch(name_lower, pat) for pat in PERSONAL_PATTERNS):
                continue
        if _should_skip(path, skip_patterns):
            continue
        try:
            if path.stat().st_size == 0:
                continue
        except OSError:
            continue
        yield path


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input", required=True, type=Path,
                        help="Root folder to walk. On Windows, use quotes for paths with spaces.")
    parser.add_argument("--collection", default=None,
                        help=f"Override auto-routing. Default: auto-pick "
                             f"'{DEFAULT_COLLECTION}' or '{PERSONAL_COLLECTION}' per file.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N files (smoke test).")
    parser.add_argument("--reembed", action="store_true",
                        help="Force re-ingest even if chunk id already exists.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Walk the tree and print what would be ingested. No embed/write.")
    parser.add_argument("--ocr-all", action="store_true",
                        help="Run OCR on every image, not just lab/COA-named ones. Slow.")
    parser.add_argument("--skip-manifest", type=Path, default=None,
                        help="File listing paths/glob patterns to skip (one per line).")
    args = parser.parse_args()

    root = args.input.expanduser().resolve()
    if not root.exists():
        print(f"ERROR: --input does not exist: {root}")
        sys.exit(1)

    skip_patterns = load_skip_manifest(args.skip_manifest)
    if skip_patterns:
        print(f"Loaded {len(skip_patterns)} skip patterns from {args.skip_manifest}")

    # Phase 1 — walk and summarize (always runs; dry-run stops here)
    files = list(iter_documents(root, skip_patterns, include_ocr=args.ocr_all))
    if args.limit:
        files = files[:args.limit]
    if not files:
        print(f"No supported files found under {root}")
        sys.exit(0)

    routing: dict[str, list[Path]] = {}
    for p in files:
        col = route_collection(p, args.collection)
        routing.setdefault(col, []).append(p)

    print(f"\nFound {len(files)} supported files under {root}")
    for col, paths in sorted(routing.items()):
        print(f"  → collection '{col}': {len(paths)} file(s)")

    if args.dry_run:
        print("\n─── dry-run detail ───")
        for col, paths in sorted(routing.items()):
            print(f"\n[{col}]")
            for p in paths:
                try:
                    size_kb = p.stat().st_size // 1024
                except OSError:
                    size_kb = 0
                print(f"  {size_kb:>7} KB  {p.suffix.lower():<6}  {p.relative_to(root)}")
        print("\n(dry-run; nothing embedded or written)")
        return

    # Phase 2 — Ollama sanity + Chroma open
    try:
        probe = ollama_client.embed(model=EMBED_MODEL, input=["ping"],
                                    options={"num_ctx": EMBED_NUM_CTX})
        dim = len(probe["embeddings"][0])
        print(f"\nOllama OK | host={OLLAMA_HOST} | model={EMBED_MODEL} | dim={dim}")
    except Exception as e:
        print(f"ERROR: Ollama not reachable: {e}")
        print(f"  Make sure Ollama daemon is running, then: ollama pull {EMBED_MODEL}")
        sys.exit(1)

    CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    collections = {
        name: client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": DISTANCE_METRIC, "embed_model": EMBED_MODEL},
        )
        for name in routing.keys()
    }
    for name, col in collections.items():
        print(f"Collection '{name}' | existing count: {col.count():,}")

    # Phase 3 — extract, chunk, embed, upsert
    total_files_done = 0
    total_chunks_new = 0
    total_chunks_skipped = 0
    total_extract_failed = 0

    for col_name, paths in sorted(routing.items()):
        collection = collections[col_name]
        existing_ids: set[str] = set()
        if not args.reembed:
            # Pull existing ids in one shot (Chroma supports get(ids=None) — grab all
            # then filter). For very large collections this could get big; consider
            # switching to per-file existence probes if that becomes a bottleneck.
            try:
                existing = collection.get(include=[])
                existing_ids = set(existing.get("ids", []))
            except Exception:
                existing_ids = set()
        print(f"\n═══ collection '{col_name}' — {len(paths)} file(s), "
              f"{len(existing_ids):,} existing ids ═══")

        pending_ids: list[str] = []
        pending_metas: list[dict] = []
        pending_docs: list[str] = []

        insert_buf_ids: list[str] = []
        insert_buf_embs: list[list[float]] = []
        insert_buf_metas: list[dict] = []
        insert_buf_docs: list[str] = []

        def flush_embeddings():
            nonlocal total_chunks_new
            if not pending_docs:
                return
            embs = embed_batch(pending_docs)
            insert_buf_ids.extend(pending_ids)
            insert_buf_embs.extend(embs)
            insert_buf_metas.extend(pending_metas)
            insert_buf_docs.extend(pending_docs)
            total_chunks_new += len(pending_docs)
            pending_ids.clear()
            pending_metas.clear()
            pending_docs.clear()

        def flush_insert():
            if not insert_buf_ids:
                return
            collection.upsert(
                ids=insert_buf_ids,
                embeddings=insert_buf_embs,
                metadatas=insert_buf_metas,
                documents=insert_buf_docs,
            )
            print(f"  ↳ upserted {len(insert_buf_ids)} chunks "
                  f"(total new in this run: {total_chunks_new})")
            insert_buf_ids.clear()
            insert_buf_embs.clear()
            insert_buf_metas.clear()
            insert_buf_docs.clear()

        for p in paths:
            src_key = str(p).replace("\\", "/")
            try:
                text = extract(p)
            except Exception as e:
                total_extract_failed += 1
                print(f"  ✗ extract failed: {p.name}  ({type(e).__name__}: {str(e)[:120]})")
                continue

            text = (text or "").strip()
            if not text:
                print(f"  · empty extraction: {p.name}")
                continue

            n_chunks_kept = 0
            n_chunks_skipped = 0
            for idx, chunk in enumerate(chunk_text(text)):
                cid = stable_id(src_key, idx)
                if cid in existing_ids and not args.reembed:
                    n_chunks_skipped += 1
                    continue
                pending_ids.append(cid)
                pending_metas.append({
                    "source": src_key,
                    "file_name": p.name,
                    "file_ext": p.suffix.lower(),
                    "chunk_index": idx,
                    "root": str(root).replace("\\", "/"),
                    "kind": "document",
                    "collection": col_name,
                })
                pending_docs.append(chunk)
                n_chunks_kept += 1
                if len(pending_docs) >= EMBED_BATCH:
                    flush_embeddings()
                if len(insert_buf_ids) >= INSERT_BATCH:
                    flush_insert()

            total_chunks_skipped += n_chunks_skipped
            total_files_done += 1
            print(f"  ✓ {p.name}  chunks_new={n_chunks_kept} skipped={n_chunks_skipped}")

        flush_embeddings()
        flush_insert()

    print("\n─── summary ───")
    print(f"  files processed: {total_files_done}")
    print(f"  chunks added:    {total_chunks_new:,}")
    print(f"  chunks skipped:  {total_chunks_skipped:,} (already in DB)")
    print(f"  extract failures: {total_extract_failed}")
    print(f"  zero-vector fallbacks: {_ZERO_VECTOR_COUNT}")
    for name, col in collections.items():
        print(f"  collection '{name}' final count: {col.count():,}")


if __name__ == "__main__":
    main()
