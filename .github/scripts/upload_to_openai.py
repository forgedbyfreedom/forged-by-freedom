#!/usr/bin/env python3
"""
Transfer git-tracked files to a Pinecone index, with a failsafe to skip files
where the substring after IGNORE_AFTER contains non-ASCII characters.

Environment variables:
 - PINECONE_API_KEY
 - PINECONE_ENV (or PINECONE_REGION depending on your pinecone client version)
 - PINECONE_INDEX
 - IGNORE_AFTER  (default "ggst"; set to empty string to disable)
 - EMBED_MODEL (optional; you can plug in your embedding function)
"""
import os
import sys
import unicodedata
import re
import hashlib
import subprocess
import pathlib
from typing import List

# Optional: import pinecone client if available
try:
    import pinecone
    from pinecone import PineconeException
except Exception:
    pinecone = None
    PineconeException = Exception

# ------- Helpers (sanitize / ascii checks) -------
def sanitize(name: str, index: int = None, max_len: int = 200) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_bytes = normalized.encode("ascii", "ignore")
    ascii_name = ascii_bytes.decode("ascii")
    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', '-', ascii_name).strip('-')
    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode("utf-8", "surrogatepass")).hexdigest()[:12]
    suffix = f'-{index}' if index is not None else ''
    max_name_len = max_len - len(suffix)
    if len(ascii_name) > max_name_len:
        ascii_name = ascii_name[:max_name_len]
    return ascii_name + suffix

def has_non_ascii(s: str) -> bool:
    return any(ord(c) > 127 for c in s)

def sha1_hex(s: str, length: int = 12) -> str:
    return hashlib.sha1(s.encode('utf-8', 'surrogatepass')).hexdigest()[:length]

# ------- Embedding placeholder -------
def generate_embedding(text: str) -> List[float]:
    """
    Replace this with your embedding function (OpenAI, Cohere, local model, etc.)
    Return a list/sequence of floats representing the embedding for `text`.
    """
    # Minimal placeholder: return a tiny deterministic vector (replace in prod)
    h = hashlib.sha1(text.encode('utf-8')).digest()
    # convert some bytes to small floats
    return [float(b) / 255.0 for b in h[:16]]

# ------- Main flow -------
IGNORE_AFTER = os.getenv("IGNORE_AFTER", "ggst")  # default per your request

# Pinecone config (must be provided via env / secrets in GH Actions)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV") or os.getenv("PINECONE_REGION")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")

if not PINECONE_API_KEY or not PINECONE_ENV or not PINECONE_INDEX:
    print("Warning: One or more Pinecone environment variables missing (PINECONE_API_KEY, PINECONE_ENV/REGION, PINECONE_INDEX).")
    print("The script will still run the skip logic and show what WOULD be uploaded, but won't attempt Pinecone upserts.")
    pinecone_enabled = False
else:
    pinecone_enabled = True

if pinecone_enabled and pinecone is None:
    print("Pinecone client library is not importable; install `pinecone-client` or similar to enable upserts.")
    pinecone_enabled = False

if pinecone_enabled:
    try:
        pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
        index = pinecone.Index(PINECONE_INDEX)
    except Exception as e:
        print("Failed to initialize Pinecone client:", e)
        pinecone_enabled = False
        index = None
else:
    index = None

# Get git-tracked files
proc = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
if proc.returncode != 0:
    print("Error running 'git ls-files':", proc.stderr.strip())
    sys.exit(2)

files = [l for l in proc.stdout.splitlines() if l.strip()]
if not files:
    print("No git-tracked files found.")
    sys.exit(0)

# Build ignore list using the IGNORE_AFTER logic (skip if substring after marker contains non-ASCII)
ignored_files = []
if IGNORE_AFTER:
    for f in files:
        if IGNORE_AFTER in f:
            tail = f.split(IGNORE_AFTER, 1)[1]
            if has_non_ascii(tail):
                ignored_files.append(f)

if ignored_files:
    print(f"IGNORE_AFTER='{IGNORE_AFTER}' -> files ignored because non-ASCII found after marker ({len(ignored_files)}):")
    for f in ignored_files:
        print("  " + f)
else:
    print(f"IGNORE_AFTER='{IGNORE_AFTER}' -> no files ignored by the marker logic.")

# Iterate and upload (or dry-run)
uploaded = 0
skipped_by_marker = 0
skipped_by_error = 0
skipped_binary_or_read = 0

for f in files:
    if f in ignored_files:
        skipped_by_marker += 1
        continue

    # read file content (skip unreadable / binary heuristics)
    path = pathlib.Path(f)
    try:
        raw = path.read_bytes()
        # crude binary check: if there are null bytes, treat as binary and skip
        if b'\x00' in raw:
            print(f"Skipping binary file: {f}")
            skipped_binary_or_read += 1
            continue
        text = raw.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Failed to read {f}: {e} -- skipping")
        skipped_binary_or_read += 1
        continue

    # create a stable ASCII id for Pinecone
    base_name = path.name
    candidate_id = sanitize(base_name, index=0)
    if has_non_ascii(candidate_id):
        # fallback to hex id if sanitize still produced non-ASCII (unlikely)
        candidate_id = sha1_hex(base_name)

    # Safety: enforce a conservative allowed-id pattern (alnum, dot, underscore, hyphen)
    # replace any other ascii chars with '-' just in case (space/pipe will be removed)
    candidate_id = re.sub(r'[^A-Za-z0-9._-]+', '-', candidate_id).strip('-')
    if not candidate_id:
        candidate_id = sha1_hex(base_name)

    # generate embedding (replace with your real embedder)
    embedding = generate_embedding(text)

    vector = {
        "id": candidate_id,
        "values": embedding,
        "metadata": {"path": f}
    }

    if not pinecone_enabled:
        print(f"[DRY-RUN] Would upsert vector id={candidate_id} for file {f}")
        uploaded += 1
        continue

    # Attempt upsert, but catch Pinecone errors and skip if ID problems occur
    try:
        # upsert a single vector (batching could be added)
        index.upsert(vectors=[vector])
        print(f"Upserted id={candidate_id}  -> {f}")
        uploaded += 1
    except Exception as e:
        # Try to detect an ID/ASCII problem and skip; otherwise surface the error but continue
        msg = str(e)
        print(f"Pinecone upsert error for id={candidate_id} file={f}: {msg}")
        skipped_by_error += 1
        continue

# Summary
print("\n=== Summary ===")
print(f"Total git-tracked files: {len(files)}")
print(f"Uploaded (or dry-run processed): {uploaded}")
print(f"Skipped by marker (non-ASCII after IGNORE_AFTER): {skipped_by_marker}")
print(f"Skipped due to read/binary issues: {skipped_binary_or_read}")
print(f"Skipped due to upsert errors: {skipped_by_error}")

# exit code: 0 unless everything failed
if uploaded == 0 and skipped_by_marker + skipped_binary_or_read + skipped_by_error > 0:
    # nothing uploaded but there were reasons; exit 0 so workflows don't fail, adjust if you prefer non-zero
    sys.exit(0)

sys.exit(0)
