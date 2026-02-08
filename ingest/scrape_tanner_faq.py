#!/usr/bin/env python3
"""
Scrape Tanner Tattered FAQ content from website
"""

import os
import re
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run(["pip3", "install", "requests", "beautifulsoup4"], capture_output=True)
    import requests
    from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent / "channels" / "@TannerTatteredFAQ"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# All known resource pages on tannertattered.com
RESOURCE_PAGES = [
    ("the-basics", "https://www.tannertattered.com/resources/the-basics"),
    ("am-i-ready-for-gear", "https://www.tannertattered.com/resources/am-i-ready-for-gear"),
    ("faqs", "https://www.tannertattered.com/faqs"),
    ("injectable-testosterone", "https://www.tannertattered.com/resources/injectable-testosterone"),
    ("hcg", "https://www.tannertattered.com/resources/hcg"),
    ("mk-677", "https://www.tannertattered.com/resources/mk-677"),
    ("bpc-157", "https://www.tannertattered.com/resources/bpc-157"),
    ("tb-500", "https://www.tannertattered.com/resources/tb-500"),
    ("sildenafil", "https://www.tannertattered.com/resources/sildenafil"),
    ("tadalafil", "https://www.tannertattered.com/resources/tadalafil"),
    ("anavar", "https://www.tannertattered.com/resources/anavar"),
    ("anadrol", "https://www.tannertattered.com/resources/anadrol"),
    ("arimidex", "https://www.tannertattered.com/resources/arimidex"),
    ("aromasin", "https://www.tannertattered.com/resources/aromasin"),
    ("nolvadex", "https://www.tannertattered.com/resources/nolvadex"),
    ("clomid", "https://www.tannertattered.com/resources/clomid"),
    ("primobolan", "https://www.tannertattered.com/resources/primobolan"),
    ("masteron", "https://www.tannertattered.com/resources/masteron"),
    ("equipoise", "https://www.tannertattered.com/resources/equipoise"),
    ("trenbolone", "https://www.tannertattered.com/resources/trenbolone"),
    ("deca-durabolin", "https://www.tannertattered.com/resources/deca-durabolin"),
    ("dianabol", "https://www.tannertattered.com/resources/dianabol"),
    ("winstrol", "https://www.tannertattered.com/resources/winstrol"),
    ("pct", "https://www.tannertattered.com/resources/pct"),
    ("blood-pressure", "https://www.tannertattered.com/resources/blood-pressure"),
    ("cholesterol", "https://www.tannertattered.com/resources/cholesterol"),
    ("hair-loss", "https://www.tannertattered.com/resources/hair-loss"),
    ("gynecomastia", "https://www.tannertattered.com/resources/gynecomastia"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def clean_text(html_content):
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove script and style elements
    for element in soup(['script', 'style', 'nav', 'header', 'footer']):
        element.decompose()

    # Get text
    text = soup.get_text(separator='\n')

    # Clean up whitespace
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]

    # Remove duplicate consecutive lines
    cleaned = []
    prev = ""
    for line in lines:
        if line != prev:
            cleaned.append(line)
        prev = line

    return '\n'.join(cleaned)


def fetch_page(name, url):
    """Fetch and save a single page."""
    output_file = OUTPUT_DIR / f"{name}.txt"

    if output_file.exists():
        print(f"  ⏭️  {name} already exists, skipping")
        return True

    try:
        print(f"  📥 Fetching: {name}")
        response = requests.get(url, headers=HEADERS, timeout=30)

        if response.status_code == 200:
            text = clean_text(response.text)

            if len(text) > 100:
                # Add source attribution
                content = f"Source: Tanner Tattered FAQ - {name}\n"
                content += f"URL: {url}\n"
                content += f"Speaker: Tanner Tattered\n"
                content += "=" * 60 + "\n\n"
                content += text

                output_file.write_text(content, encoding='utf-8')
                print(f"  ✅ Saved: {name} ({len(text)} chars)")
                return True
            else:
                print(f"  ⚠️  {name} - too short, skipping")
                return False
        else:
            print(f"  ❌ {name} - HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"  ❌ {name} - Error: {e}")
        return False


def main():
    print("=" * 60)
    print("  TANNER TATTERED FAQ SCRAPER")
    print("=" * 60)
    print(f"Output: {OUTPUT_DIR}")
    print(f"Pages to fetch: {len(RESOURCE_PAGES)}")
    print()

    success = 0
    failed = 0

    for name, url in RESOURCE_PAGES:
        if fetch_page(name, url):
            success += 1
        else:
            failed += 1
        time.sleep(2)  # Be polite

    print()
    print("=" * 60)
    print(f"  COMPLETE: {success} saved, {failed} failed")
    print("=" * 60)

    # Create channel.url file for consistency
    url_file = OUTPUT_DIR / "channel.url"
    url_file.write_text("https://www.tannertattered.com/faqs\n")


if __name__ == "__main__":
    main()
