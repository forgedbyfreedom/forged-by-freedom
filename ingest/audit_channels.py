#!/usr/bin/env python3
"""
Dead Channel Audit
------------------
Tests every channel.url file to see if the YouTube channel is still reachable.
Outputs a report of dead/redirected/live channels.

Usage:
    python3 audit_channels.py              # full audit
    python3 audit_channels.py --fast       # HEAD requests only (faster but less accurate)
"""

import os
import sys
import time
import argparse
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"


def check_channel(url, fast=False):
    """Check if a YouTube channel URL is reachable.

    Returns: (status, detail)
        status: 'live', 'dead', 'redirect', 'error'
        detail: HTTP status code or error message
    """
    url = url.strip()
    if not url:
        return "empty", "No URL in file"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        method = "HEAD" if fast else "GET"
        req = Request(url, method=method, headers=headers)
        resp = urlopen(req, timeout=15)

        # Check if we got redirected to a different channel or error page
        final_url = resp.url
        if "/channel/UC" in final_url and "/@" in url:
            return "live", f"200 (resolved to {final_url})"

        # YouTube returns 200 even for some dead channels but shows error content
        if not fast:
            content = resp.read(50000).decode("utf-8", errors="ignore")
            if "This page isn" in content or "isn't available" in content:
                return "dead", "Page says 'not available'"
            if '"externalId"' not in content and '"channelId"' not in content:
                return "dead", "No channel ID found in page"

        return "live", f"{resp.status}"

    except HTTPError as e:
        if e.code == 404:
            return "dead", "404 Not Found"
        elif e.code == 403:
            return "error", "403 Forbidden (rate limited?)"
        else:
            return "error", f"HTTP {e.code}"
    except URLError as e:
        return "error", f"URL Error: {e.reason}"
    except Exception as e:
        return "error", str(e)


def audit(fast=False):
    """Audit all channels for dead URLs."""
    # Find all channel.url files
    url_files = sorted(CHANNELS_DIR.glob("*/channel.url"))
    total = len(url_files)

    print(f"\n{'='*60}")
    print(f"CHANNEL AUDIT — {total} channels")
    print(f"Mode: {'HEAD (fast)' if fast else 'GET (thorough)'}")
    print(f"{'='*60}\n")

    results = {"live": [], "dead": [], "redirect": [], "error": [], "empty": []}

    for i, url_file in enumerate(url_files, 1):
        channel = url_file.parent.name
        url = url_file.read_text().strip()

        # Count transcripts in channel dir
        txt_count = len(list(url_file.parent.glob("*.txt")))
        mp3_count = len(list(url_file.parent.glob("*.mp3")))

        status, detail = check_channel(url, fast=fast)
        results[status].append((channel, url, detail, txt_count, mp3_count))

        icon = {"live": "✅", "dead": "💀", "redirect": "↪️ ", "error": "⚠️ ", "empty": "❓"}
        print(f"{icon[status]} [{i}/{total}] {channel:<35} {status:<8} {detail}")

        # Rate limit to avoid YouTube blocking
        time.sleep(0.5 if fast else 1.0)

    # Summary
    print(f"\n{'='*60}")
    print("AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Live:     {len(results['live'])}")
    print(f"💀 Dead:     {len(results['dead'])}")
    print(f"↪️  Redirect: {len(results['redirect'])}")
    print(f"⚠️  Error:    {len(results['error'])}")
    print(f"❓ Empty:    {len(results['empty'])}")

    if results["dead"]:
        print(f"\n{'='*60}")
        print("DEAD CHANNELS (should remove or update)")
        print(f"{'='*60}")
        for channel, url, detail, txts, mp3s in results["dead"]:
            content_note = f" ({txts} txts, {mp3s} mp3s)" if txts or mp3s else " (empty)"
            print(f"  💀 {channel:<35} {url}")
            print(f"     Reason: {detail}{content_note}")

    if results["error"]:
        print(f"\n{'='*60}")
        print("ERRORS (may need manual check)")
        print(f"{'='*60}")
        for channel, url, detail, txts, mp3s in results["error"]:
            print(f"  ⚠️  {channel:<35} {detail}")

    # Write report file
    report_path = BASE_DIR / "channel_audit_report.txt"
    with open(report_path, "w") as f:
        f.write(f"Channel Audit Report\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total channels: {total}\n\n")
        for status_key in ["dead", "error", "redirect", "live"]:
            f.write(f"\n{'='*60}\n")
            f.write(f"{status_key.upper()} ({len(results[status_key])})\n")
            f.write(f"{'='*60}\n")
            for channel, url, detail, txts, mp3s in results[status_key]:
                f.write(f"{channel}\t{url}\t{detail}\t{txts} txts\t{mp3s} mp3s\n")

    print(f"\n📄 Report saved to: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit YouTube channel URLs")
    parser.add_argument("--fast", action="store_true", help="Use HEAD requests (faster)")
    args = parser.parse_args()
    audit(fast=args.fast)
