#!/usr/bin/env python3
"""
FBF Scraper Orchestrator
Runs all scrapers in sequence, then ingests new content into local Chroma.
Safe to re-run — all scrapers skip already-saved files.
Reddit scraper uses the public JSON API — no credentials required.

Usage:
  python run_all.py                   # everything
  python run_all.py --only janoshik   # single spider
  python run_all.py --only meso_rx
  python run_all.py --only reddit
  python run_all.py --skip-ingest     # scrapers only, skip Chroma ingest
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
INGEST_DIR = HERE.parent  # forged-by-freedom/ingest/

# The residential AT&T IP — Janoshik WAF blocks it.
# ProtonVPN must be on when running Janoshik.
HOME_IP = "172.12.76.33"


def _current_ip() -> str:
    try:
        import urllib.request
        return urllib.request.urlopen("https://ifconfig.me", timeout=8).read().decode().strip()
    except Exception:
        return ""


def _vpn_active() -> bool:
    """True if ProtonVPN WireGuard service is running (fastest check, no network call)."""
    try:
        out = subprocess.check_output(
            ["sc", "query", "ProtonVPN WireGuard"],
            stderr=subprocess.DEVNULL, text=True
        )
        return "RUNNING" in out
    except Exception:
        return False


def run_scrapy(spider: str):
    print(f"\n{'='*60}")
    print(f"  SCRAPY — {spider}")
    print(f"{'='*60}\n")
    result = subprocess.run(
        [sys.executable, "-m", "scrapy", "crawl", spider],
        cwd=HERE,
    )
    return result.returncode == 0


def run_reddit():
    print(f"\n{'='*60}")
    print(f"  REDDIT SCRAPER (Arctic Shift)")
    print(f"{'='*60}\n")
    result = subprocess.run(
        [sys.executable, str(HERE / "reddit_scraper.py")],
    )
    return result.returncode == 0


def run_chroma_ingest():
    print(f"\n{'='*60}")
    print(f"  CHROMA INGEST (nomic-embed-text -> local DB)")
    print(f"{'='*60}\n")
    # Use the ingest venv's Python which has chromadb + ollama installed
    venv_py = INGEST_DIR / ".venv" / "Scripts" / "python.exe"
    py = str(venv_py) if venv_py.exists() else sys.executable
    result = subprocess.run(
        [py, str(INGEST_DIR / "ingest_to_chroma.py")],
        cwd=str(INGEST_DIR),
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["meso_rx", "janoshik", "reddit"])
    parser.add_argument("--skip-ingest", action="store_true",
                        help="Skip Chroma ingest step after scrapers")
    args = parser.parse_args()

    results = {}

    if args.only == "meso_rx" or not args.only:
        results["meso_rx"] = run_scrapy("meso_rx")

    if args.only == "janoshik" or not args.only:
        if _vpn_active():
            print("VPN: ProtonVPN active — running Janoshik")
            results["janoshik"] = run_scrapy("janoshik")
        else:
            print("VPN: ProtonVPN not active — skipping Janoshik (WAF blocks home IP)")
            print("     Turn on ProtonVPN and re-run with --only janoshik to scrape it.")
            results["janoshik"] = False

    if args.only == "reddit" or not args.only:
        results["reddit"] = run_reddit()

    # Always ingest after a full scraper run (not when running a single spider)
    if not args.only and not args.skip_ingest:
        results["chroma_ingest"] = run_chroma_ingest()

    print(f"\n{'='*60}")
    print("  SCRAPER RUN SUMMARY")
    print(f"{'='*60}")
    for name, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {name:20s} {status}")


if __name__ == "__main__":
    main()
