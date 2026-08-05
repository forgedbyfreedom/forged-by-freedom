#!/usr/bin/env python3
"""
Ship transcript text to the FBF AI service /ingest endpoint (Qdrant-backed).
 
Replaces ingest_to_wordpress.py, which POSTed to the WordPress /rag/upsert
endpoint (wrong store: fills wp_fbf_rag_chunks, whose PHP cosine scan can crash
the site) and returned HTTP 520 every run. This targets the same endpoint the
working PC pipeline uses:
    POST {FBF_AI_URL}/ingest   header X-API-Key   body {"source","text"}
The server chunks + embeds server-side and upserts into Qdrant (fbf_pinecone),
idempotent on deterministic IDs. No OpenAI key needed here.
"""
 
import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.error
 
BASE       = os.environ.get("FBF_AI_URL", "https://ai.serverborn.com").rstrip("/")
KEY        = os.environ.get("FBF_AI_API_KEY", "")
ENDPOINT   = BASE + "/ingest"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vps_ingest_state.json")
MAX_FILES  = int(os.environ.get("MAX_CHUNKS_PER_RUN", "0") or "0")
 
ROOTS = ["channels", "transcripts", "ingest/channels", "ingest/transcripts"]
EXTS  = (".txt", ".md", ".vtt")
RETRY_CODES = (408, 429, 500, 502, 503, 504, 520, 522, 524)
 
 
def sha1_bytes(b):
    return hashlib.sha1(b).hexdigest()
 
 
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}
 
 
def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)
 
 
def iter_files():
    seen_root = False
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        seen_root = True
        for dirpath, _dirs, names in os.walk(root):
            for n in names:
                low = n.lower()
                if not low.endswith(EXTS):
                    continue
                if low.startswith("master_transcript"):
                    continue
                yield os.path.join(dirpath, n)
    if not seen_root:
        print("WARNING: none of the transcript roots exist: %s" % ", ".join(ROOTS), file=sys.stderr)
 
 
def post(source, text):
    body = json.dumps({"source": source, "text": text}).encode("utf-8")
    for attempt in range(5):
        req = urllib.request.Request(ENDPOINT, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if KEY:
            req.add_header("X-API-Key", KEY)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return True, r.status
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "ignore")[:200]
            except Exception:
                pass
            if e.code in RETRY_CODES and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            return False, "HTTP %s %s" % (e.code, detail)
        except Exception as e:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            return False, str(e)
    return False, "retries exhausted"
 
 
def main():
    if not KEY:
        print("FBF_AI_API_KEY missing", file=sys.stderr)
        sys.exit(1)
 
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=30) as r:
            print("Preflight OK: %s/health reachable (HTTP %s)." % (BASE, r.status))
    except Exception as e:
        print("Preflight WARNING: /health unreachable: %s" % e)
 
    state = load_state()
    files = sorted(iter_files())
    print("Scanning %d transcript files. State has %d known." % (len(files), len(state)))
 
    sent = skipped = failed = 0
    for path in files:
        rel = os.path.relpath(path)
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except Exception as e:
            print("skip (read error) %s: %s" % (rel, e))
            continue
 
        h = sha1_bytes(raw)
        if state.get(rel) == h:
            skipped += 1
            continue
 
        text = raw.decode("utf-8", "ignore").strip()
        if not text:
            state[rel] = h
            continue
 
        ok, info = post(rel, text)
        if ok:
            state[rel] = h
            sent += 1
            if sent % 200 == 0:
                save_state(state)
                print("... %d sent, %d skipped so far" % (sent, skipped))
        else:
            failed += 1
            print("FAIL %s -> %s" % (rel, info))
 
        if MAX_FILES and sent >= MAX_FILES:
            print("Hit MAX_CHUNKS_PER_RUN=%d — stopping this run (resumes next run)." % MAX_FILES)
            break
 
    save_state(state)
    print("Done. sent=%d  skipped=%d  failed=%d  total=%d" % (sent, skipped, failed, len(files)))
 
    if files and sent == 0 and skipped == 0 and failed > 0:
        sys.exit(2)
 
 
if __name__ == "__main__":
    main()
 
