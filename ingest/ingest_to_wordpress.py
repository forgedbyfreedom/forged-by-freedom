#!/usr/bin/env python3
"""
DEPRECATED - do not use.

This script used to POST transcripts to the WordPress /rag/upsert endpoint,
which targeted the wrong store (wp_fbf_rag_chunks) and returned HTTP 520 on
every run. It has been retired.

The nightly RAG ingest now runs ingest_to_vps.py, which POSTs to the FBF AI
service /ingest endpoint (Qdrant-backed) and works. See .github/workflows/ingest.yml.

This file is kept only as a no-op so any stale workflow, trigger, or manual
call exits cleanly (exit 0) instead of failing. It embeds and uploads nothing.
"""
import sys

MSG = (
    "ingest_to_wordpress.py is DEPRECATED and does nothing.\n"
    "The nightly RAG ingest now runs ingest_to_vps.py (POSTs to the FBF AI\n"
    "service /ingest endpoint, Qdrant-backed). Update whatever invoked this\n"
    "to call ingest_to_vps.py instead.\n"
)

if __name__ == "__main__":
    sys.stdout.write(MSG)
    sys.exit(0)
