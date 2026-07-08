# Document ingest — `ingest_documents_to_chroma.py`

Companion to `ingest_to_chroma.py`. Where that script handles
YouTube/forum transcripts organized as `channels/@ChannelName/*.txt`,
this one handles standalone **documents** — books, PDFs, program
guides, bloodwork PDFs, supplier COAs — under any folder tree you
point it at.

## Where the data ends up

Same local ChromaDB: `C:/AI/chroma_db_local`. Two new collections
alongside `forum_content`:

| Collection | Contents |
|---|---|
| `bodybuilding_reference` | Books, program PDFs, course PDFs, training / anabolics reference |
| `personal_medical` | Your bloodwork, supplier COAs, anything matching `*bloodwork*`, `*labs*`, `*coa*`, `*panel*`, `*zhuoyue*`, `precision*` |

Routing is automatic per file name. Override with `--collection <name>`
to force everything into one bucket.

Retrieval-side note: point the AI Coach retriever at
`bodybuilding_reference` for general fitness / nutrition / anabolics
questions. Keep `personal_medical` gated (member-only, or your-eyes-only)
because it contains PII (your name, dates, values) and supplier-specific
COA data.

## First run (on the Windows PC where Ollama runs)

Install extractors — one-time:

```powershell
pip install pymupdf ebooklib beautifulsoup4 python-docx pytesseract Pillow
# Tesseract binary (for image OCR of COAs):
winget install UB-Mannheim.TesseractOCR
```

Dry run first — walk the tree, see what routes where, no writes:

```powershell
python ingest\ingest_documents_to_chroma.py `
    --input "C:\Users\Antonelli\Downloads" `
    --dry-run
```

You'll get a summary like:

```
Found 84 supported files under C:\Users\Antonelli\Downloads
  → collection 'bodybuilding_reference': 78 file(s)
  → collection 'personal_medical': 6 file(s)
```

Look at the per-file breakdown. If anything ends up in the wrong
collection, either rename the file/folder to match the routing
patterns, or use `--collection` to force it.

Real run:

```powershell
python ingest\ingest_documents_to_chroma.py `
    --input "C:\Users\Antonelli\Downloads"
```

Resumable — reruns skip chunks already in the DB via a stable ID
(`sha1(source_path)|chunk_index`).

## Excluding specific files

Create `ingest/skip_paths.txt`, one substring or glob per line:

```
# any path containing this substring is skipped
[FreeCoursesOnline.Me]
35927-
# skip a whole folder:
Downloads/attachments
# glob (matched against normalized forward-slash lowercase path):
*fbf-agents*
```

Then:

```powershell
python ingest\ingest_documents_to_chroma.py `
    --input "C:\Users\Antonelli\Downloads" `
    --skip-manifest ingest\skip_paths.txt
```

## What's supported

| Extension | Extractor | Notes |
|---|---|---|
| `.pdf` | PyMuPDF (falls back to pdfplumber) | Both text-based and scanned (if scanned, text will be sparse — consider OCR pass separately) |
| `.epub` | ebooklib + BeautifulSoup | |
| `.docx` | python-docx | Body text only; skips tables/headers |
| `.txt`, `.md` | direct read | UTF-8 → UTF-8-sig → latin-1 → cp1252 fallback chain |
| `.jpg`, `.jpeg`, `.png`, `.webp` | pytesseract | **Only** run on files matching the personal-collection patterns (COAs, labs) unless you pass `--ocr-all` |

## What's silently skipped

`.torrent`, `.zip`, `.rar`, `.7z`, `.iso`, `.exe`, video files
(`.mp4`, `.mkv`, `.mov`, ...), audio files (`.mp3`, `.wav`, ...).

Torrent files are metadata pointers to content, not the content
itself — nothing to ingest. If you want the underlying content,
download it via a torrent client first, then re-run the ingest
against the extracted folder.

## Chunking + embedding — matches the existing pipeline

- Tokenizer: `tiktoken cl100k_base`
- Chunk size: 3,000 tokens (same as `ingest_to_pinecone.py` and
  `ingest_to_chroma.py`)
- Embedding: `nomic-embed-text` via Ollama (768-d)
- Distance: cosine

Same as your existing pipelines, so retrieval quality across
collections is consistent — a query hitting `forum_content` and
`bodybuilding_reference` scores each collection the same way.

## Troubleshooting

**"Ollama not reachable"** — same problem the ECHO thread saw with
`192.168.1.130`. Confirm Ollama is running on your Windows box:
```powershell
ollama list                # should print installed models
curl http://127.0.0.1:11434/api/tags   # should return JSON
```
Then verify the embed model is pulled:
```powershell
ollama pull nomic-embed-text
```

**"PDF extraction requires PyMuPDF"** — `pip install pymupdf`.
`pdfplumber` is the automatic fallback if PyMuPDF isn't there.

**"zero-vector fallback"** warnings — a chunk exceeded the model's
context after multiple retries. It's still ingested (with a zero
vector), just won't be findable via retrieval. If you see many of
these, the source PDF is probably scanned/image-only — needs a real
OCR pass first.

**Duplicate chunks** — reruns are idempotent by design (stable ID
per path+chunk). Pass `--reembed` if you want to force overwrite
after tweaking chunking.
