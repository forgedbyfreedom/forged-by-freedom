#!/usr/bin/env python3
"""
Forged By Freedom - VPS RAG Ingest (replaces Pinecone)
------------------------------------------------------
Embeds channel transcripts with OpenAI text-embedding-3-large (same model the
WordPress AI Coach uses to embed queries) and upserts them to the ONE knowledge
store on the VPS (WordPress table wp_fbf_rag_chunks) via the /fbf/v1/rag/upsert
endpoint. No Pinecone.

INCREMENTAL by design so nightly runs are cheap: a state file records the
content hash of every chunk already embedded; only new or changed chunks are
re-embedded and sent. The first run embeds the whole corpus once (one-time
cost); after that, only newly added/edited transcripts cost anything.

FAIL-FAST: a billing/quota or auth rejection from OpenAI stops the run in
seconds with a plain-English message. These never succeed on retry, so the
job does NOT loop for hours on them (see QuotaError / preflight).

Env (GitHub Action secrets):
  OPENAI_API_KEY   - embeddings
  WP_INGEST_URL    - https://forgedbyfreedom.net/wp-json/fbf/v1/rag/upsert
  WP_INGEST_KEY    - the "Ingest secret" from wp-admin > Dashboard > AI Knowledge (RAG)
Optional:
  MAX_CHUNKS_PER_RUN - cap new chunks embedded per run (default 100000). Lower it
                       (e.g. 6000) to spread the first full embed across several
                       nightly runs and bound each night's cost.
  RAG_NAMESPACE      - default 'transcripts'
"""
import os, re, sys, json, time, hashlib, urllib.request, urllib.error
from pathlib import Path

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def toks(t): return _enc.encode(t)
    def detok(t): return _enc.decode(t)
except Exception:
    # Fallback: approximate by characters (~4 chars/token) if tiktoken absent.
    def toks(t): return list(t)
    def detok(t): return "".join(t)

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
WP_INGEST_URL  = os.environ["WP_INGEST_URL"]
WP_INGEST_KEY  = os.environ["WP_INGEST_KEY"]
EMBED_MODEL    = "text-embedding-3-large"
CHUNK_TOKENS   = 3000
EMBED_BATCH    = 16
NAMESPACE      = os.environ.get("RAG_NAMESPACE", "transcripts")
MAX_NEW        = int(os.environ.get("MAX_CHUNKS_PER_RUN", "100000"))

BASE = Path(__file__).parent
CHANNELS = BASE / "channels"
STATE = BASE / ".ingest_state.json"


class QuotaError(Exception):
    """Non-retryable OpenAI failure: billing/quota exhausted or bad key."""
    pass


def quota_halt(detail=""):
    sys.stderr.write(
        "\n==================== INGEST HALTED (billing) ====================\n"
        "OpenAI rejected the embedding request as insufficient_quota / auth.\n"
        "The OPENAI_API_KEY has no available credit, so NO embeddings can be\n"
        "created and nothing is saved to the RAG store. Retrying cannot help.\n\n"
        "FIX: platform.openai.com > Settings > Billing > add a payment method\n"
        "and buy credits (a few dollars covers the whole corpus once). This is\n"
        "separate from any ChatGPT subscription.\n"
        + ("\nOpenAI said: " + detail.strip()[:500] + "\n" if detail else "")
        + "=================================================================\n")
    sys.exit(78)  # config/billing problem, distinct from transient failure


def md5(s): return hashlib.md5(s.encode("utf-8", "ignore")).hexdigest()

def extract_channel(p: Path):
    for part in p.parts:
        if part.startswith("@"):
            return part
    return "unknown"

def extract_video_id(name):
    m = re.search(r'\[([A-Za-z0-9_-]{11})\]', name)
    return m.group(1) if m else ""

def extract_title(name):
    n = name[:-4] if name.lower().endswith(".txt") else name
    return re.sub(r'\s*\[[A-Za-z0-9_-]{11}\]$', '', n).strip()

def chunk(text):
    t = toks(text)
    for i in range(0, len(t), CHUNK_TOKENS):
        yield detok(t[i:i+CHUNK_TOKENS])

def embed_batch(texts):
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode()
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request("https://api.openai.com/v1/embeddings",
                                         data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r:
                return [d["embedding"] for d in json.load(r)["data"]]
        except urllib.error.HTTPError as e:
            try: err_body = e.read().decode("utf-8", "ignore")
            except Exception: err_body = ""
            # Hard stop, never retried: quota exhausted or bad/blocked key.
            if e.code == 429 and "insufficient_quota" in err_body:
                raise QuotaError(err_body)
            if e.code in (401, 403):
                raise QuotaError(err_body or f"auth error {e.code}")
            # Transient (true rate-limit, 5xx): exponential backoff then retry.
            last = e
            if attempt == 4: raise
            time.sleep(min(30, 2 ** attempt))
        except Exception as e:
            last = e
            if attempt == 4: raise
            time.sleep(2 * (attempt + 1))
    if last: raise last

def wp_upsert(chunks, replace=False):
    body = json.dumps({"namespace": NAMESPACE, "replace": replace, "chunks": chunks}).encode()
    req = urllib.request.Request(WP_INGEST_URL, data=body,
        headers={"Content-Type": "application/json", "X-FBF-Ingest-Key": WP_INGEST_KEY})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)

def preflight():
    """Verify the key can actually embed BEFORE scanning the corpus, so a
    billing problem fails in seconds with a clear message instead of deep
    into the run."""
    try:
        embed_batch(["preflight ping"])
        print("Preflight OK: OpenAI embeddings reachable.")
    except QuotaError as q:
        quota_halt(str(q))

def main():
    if not CHANNELS.exists():
        print("No channels dir at", CHANNELS); sys.exit(1)
    preflight()
    state = {}
    if STATE.exists():
        try: state = json.load(open(STATE))
        except Exception: state = {}
    files = sorted(CHANNELS.rglob("*.txt"))
    print(f"Scanning {len(files)} transcript files. State has {len(state)} known chunks.")
    pending, new_state, embedded, skipped = [], dict(state), 0, 0

    def flush(batch):
        nonlocal embedded
        vecs = embed_batch([c["text"] for c in batch])
        payload = [{"id": c["id"], "source": c["source"], "text": c["text"], "embedding": v}
                   for c, v in zip(batch, vecs)]
        wp_upsert(payload, replace=False)
        for c in batch: new_state[c["id"]] = c["hash"]
        embedded += len(batch)
        # persist state as we go so a mid-run failure doesn't re-bill everything
        json.dump(new_state, open(STATE, "w"))
        print(f"  embedded {embedded} new chunks so far...")

    try:
        for f in files:
            channel = extract_channel(f)
            title = extract_title(f.name)
            vid = extract_video_id(f.name)
            try: text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception: continue
            if not text.strip(): continue
            source = f"{channel} - {title}" if title else channel
            for i, ch in enumerate(chunk(text)):
                cid = md5(f"{channel}|{vid}|{i}")
                h = md5(ch)
                if state.get(cid) == h:
                    skipped += 1
                    continue
                pending.append({"id": cid, "source": source, "text": ch, "hash": h})
                if embedded + len(pending) >= MAX_NEW:
                    break
                if len(pending) >= EMBED_BATCH:
                    flush(pending); pending = []
            if embedded >= MAX_NEW:
                print(f"Hit MAX_CHUNKS_PER_RUN={MAX_NEW}; stopping this run (will continue next run).")
                break
        if pending and embedded < MAX_NEW:
            flush(pending)
    except QuotaError as q:
        # Billing ran out mid-run. State is persisted incrementally, so the
        # next run resumes exactly where this stopped once credit is added.
        json.dump(new_state, open(STATE, "w"))
        quota_halt(str(q))

    json.dump(new_state, open(STATE, "w"))
    print(f"DONE. embedded {embedded} new/changed chunks, skipped {skipped} unchanged. store namespace='{NAMESPACE}'.")

if __name__ == "__main__":
    main()
