#!/usr/bin/env python3
"""
Ergo-Log.com Research Article Scraper
Pulls supplement/steroid/compound research summaries.
Targets bodybuilding-relevant categories: steroids, peptides, fat loss,
performance, hormones, longevity.
"""

import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

try:
    from curl_cffi import requests  # Chrome TLS fingerprint — bypasses WAF
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.run(["pip3", "install", "curl_cffi", "beautifulsoup4", "--break-system-packages"],
                   capture_output=True)
    from curl_cffi import requests
    from bs4 import BeautifulSoup

IMPERSONATE = "chrome124"

BASE_URL = "https://www.ergo-log.com"
OUTPUT_DIR = Path(__file__).parent / "channels" / "@ErgoLog"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# High-value category pages on ergo-log.com
CATEGORIES = [
    "anabolicsteroids",
    "sarms",
    "peptides",
    "growthhormone",
    "fatburners",
    "testosterone",
    "insulinandglucose",
    "hormones",
    "creatine",
    "aminoacids",
    "performance",
    "longevity",
    "brainboosters",
]

# Keywords to prioritize articles (skip off-topic ones)
RELEVANT_KEYWORDS = {
    "steroid", "testosterone", "anavar", "trenbolone", "deca", "dianabol",
    "winstrol", "masteron", "primobolan", "boldenone", "anadrol", "sarm",
    "lgd", "rad", "mk-677", "mk677", "ostarine", "cardarine", "peptide",
    "igf", "hgh", "growth hormone", "ghrp", "cjc", "ipamorelin", "bpc",
    "tb-500", "fat loss", "fat burn", "weight loss", "clenbuterol", "dnp",
    "retatrutide", "semaglutide", "tirzepatide", "glp-1", "insulin",
    "cortisol", "estrogen", "progesterone", "dhea", "pregnenolone",
    "creatine", "beta-alanine", "caffeine", "protein", "leucine",
    "muscle", "hypertrophy", "strength", "recovery", "sleep", "longevity",
    "mitochondria", "ampk", "mtor", "rapamycin", "metformin", "nad",
    "nmn", "resveratrol", "berberine", "carnitine", "coq10",
}


def is_relevant(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in RELEVANT_KEYWORDS)


def get_article_links(category: str) -> list[tuple[str, str]]:
    """Fetch all article links from a category page (handles pagination)."""
    links = []
    page = 1
    while True:
        url = f"{BASE_URL}/{category}.html" if page == 1 else f"{BASE_URL}/{category}{page}.html"
        try:
            r = requests.get(url, headers=HEADERS, impersonate=IMPERSONATE, timeout=20)
            if r.status_code == 404:
                break
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            found = False
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if (href.endswith(".html") and
                        not href.startswith("http") and
                        href not in ("index.html", "us.html", "contact.html") and
                        len(text) > 15):
                    full_url = urljoin(BASE_URL + "/", href)
                    if (full_url, text) not in links:
                        links.append((full_url, text))
                        found = True
            if not found:
                break
            page += 1
            time.sleep(0.5)
        except Exception:
            break
    return links


def clean_article(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "form", ".sidebar", ".widget", ".comments"]):
        tag.decompose()
    main = (soup.find("div", class_=re.compile(r"entry|post|article|content")) or
            soup.find("article") or soup.find("main") or soup)
    text = main.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and len(l) > 5]
    deduped, prev = [], ""
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line
    return "\n".join(deduped)


def scrape_article(url: str, title: str) -> bool:
    slug = re.sub(r"[^\w-]", "", url.split("/")[-1].replace(".html", ""))
    out = OUTPUT_DIR / f"{slug}.txt"
    if out.exists():
        return True
    try:
        r = requests.get(url, headers=HEADERS, impersonate=IMPERSONATE, timeout=30)
        if r.status_code != 200:
            return False
        text = clean_article(r.text)
        if len(text.split()) < 80:
            return False
        content = f"Source: Ergo-Log.com — Research Summary\n"
        content += f"Title: {title}\n"
        content += f"URL: {url}\n"
        content += f"Speaker: Ergo-Log Research Database\n"
        content += "=" * 60 + "\n\n"
        content += text
        out.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def main():
    print("=" * 60)
    print("  ERGO-LOG RESEARCH SCRAPER")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    all_links: dict[str, str] = {}

    for cat in CATEGORIES:
        print(f"\n📂 Category: {cat}")
        links = get_article_links(cat)
        relevant = [(u, t) for u, t in links if is_relevant(t)]
        print(f"   Found {len(links)} articles, {len(relevant)} relevant")
        for url, title in relevant:
            all_links[url] = title
        time.sleep(1)

    print(f"\n🔗 Total unique relevant articles: {len(all_links)}")
    print("📥 Scraping...\n")

    ok = fail = skip = 0
    for i, (url, title) in enumerate(all_links.items(), 1):
        out_slug = re.sub(r"[^\w-]", "", url.split("/")[-1].replace(".html", ""))
        if (OUTPUT_DIR / f"{out_slug}.txt").exists():
            skip += 1
            continue
        success = scrape_article(url, title)
        if success:
            ok += 1
            print(f"  ✅ [{i}/{len(all_links)}] {title[:70]}")
        else:
            fail += 1
        time.sleep(1.2)

    (OUTPUT_DIR / "channel.url").write_text("https://www.ergo-log.com\n")
    print(f"\n✅ Done — {ok} saved, {skip} skipped, {fail} failed")
    print(f"   Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
