#!/usr/bin/env python3
# encoding: utf-8
"""
Produce deterministic ASCII-only Pinecone vector IDs from filenames or strings.
"""
import re
import unicodedata
import hashlib
from typing import Optional

def sanitize_vector_id(name: str, index: Optional[int] = None, max_len: int = 200) -> str:
    """
    Turn an arbitrary filename (or string) into a safe ASCII-only ID suitable for Pinecone.
    - Normalizes Unicode (NFKD) and removes diacritics.
    - Drops non-ASCII bytes.
    - Replaces runs of characters not in [A-Za-z0-9._-] with a single '-'.
    - Falls back to a deterministic SHA1-derived hex prefix if result would be empty.
    - Optionally appends an index suffix (e.g. -0) for chunked vectors.
    - Ensures final length <= max_len.
    """
    if name is None:
        name = ""

    # Normalize and remove diacritics; then drop non-ascii bytes
    normalized = unicodedata.normalize("NFKD", name)
    ascii_bytes = normalized.encode("ascii", "ignore")
    ascii_name = ascii_bytes.decode("ascii")

    # Replace runs of unacceptable characters with single dash
    ascii_name = re.sub(r"[^A-Za-z0-9\._-]+", "-", ascii_name).strip("-")

    # If nothing left, fall back to deterministic hash prefix (12 chars)
    if not ascii_name:
        ascii_name = hashlib.sha1(name.encode("utf-8", "surrogatepass")).hexdigest()[:12]

    # Append index suffix if provided
    suffix = f"-{index}" if index is not None else ""
    # Ensure we don't exceed max_len
    max_name_len = max_len - len(suffix)
    if len(ascii_name) > max_name_len:
        ascii_name = ascii_name[:max_name_len]

    return ascii_name + suffix
