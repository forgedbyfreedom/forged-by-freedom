#!/usr/bin/env python3
"""
Forged By Freedom — PubMed Research Fetcher
--------------------------------------------
Fetches abstracts from PubMed for fitness/performance topics.
Uses NCBI E-utilities API (free, no key required for <3 req/sec).

Usage:
    python fetch_pubmed.py                    # Fetch all topics
    python fetch_pubmed.py --topic "creatine" # Fetch specific topic
    python fetch_pubmed.py --max 100          # Limit per topic
"""

import os
import re
import time
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# ─── Config ───────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "channels" / "@PubMed"
CACHE_FILE = OUTPUT_DIR / ".fetched_ids.json"

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MAX_PER_TOPIC = 500
SLEEP_BETWEEN = 0.4  # Stay under rate limit

# ─── Topics to search ─────────────────────────────────────────
TOPICS = [
    # Muscle & Training
    "resistance training muscle hypertrophy",
    "strength training adaptations",
    "muscle protein synthesis exercise",
    "skeletal muscle hypertrophy mechanisms",
    "neuromuscular adaptations strength",
    "eccentric training muscle damage",
    "training volume muscle growth",
    "training frequency hypertrophy",

    # Performance
    "athletic performance enhancement",
    "exercise performance nutrition",
    "recovery exercise training",
    "overtraining syndrome athletes",
    "periodization training athletes",
    "high intensity interval training",

    # Nutrition
    "protein intake muscle mass",
    "creatine supplementation performance",
    "beta alanine exercise performance",
    "caffeine athletic performance",
    "branched chain amino acids muscle",
    "whey protein muscle synthesis",
    "nutrient timing exercise",
    "carbohydrate exercise performance",

    # Hormones & Metabolism
    "testosterone muscle mass",
    "growth hormone exercise",
    "insulin like growth factor muscle",
    "cortisol exercise stress",
    "thyroid hormone metabolism exercise",
    "leptin ghrelin appetite exercise",

    # Anabolic agents (research context)
    "anabolic steroids muscle mass review",
    "testosterone replacement therapy",
    "selective androgen receptor modulators",
    "growth hormone deficiency treatment",
    "peptide hormones performance",

    # Body composition
    "body composition assessment methods",
    "fat loss preservation muscle mass",
    "metabolic adaptation weight loss",
    "brown adipose tissue thermogenesis",
    "visceral fat health outcomes",

    # Cardiovascular
    "cardiovascular adaptations exercise",
    "heart rate variability training",
    "blood pressure exercise intervention",
    "endothelial function exercise",

    # Recovery & Injury
    "muscle recovery post exercise",
    "sleep athletic performance",
    "cold water immersion recovery",
    "foam rolling muscle recovery",
    "tendon adaptation resistance training",
    "injury prevention athletes",

    # Aging & Longevity
    "sarcopenia resistance training",
    "aging muscle mass strength",
    "longevity exercise intervention",
    "healthspan physical activity",
    "mitochondrial function exercise aging",

    # Specific conditions
    "type 2 diabetes exercise intervention",
    "obesity exercise weight loss",
    "metabolic syndrome exercise",
    "osteoporosis resistance training",
    "low back pain exercise therapy",
]

# ─── Helpers ──────────────────────────────────────────────────
def load_cache():
    if CACHE_FILE.exists():
        return set(json.loads(CACHE_FILE.read_text()))
    return set()

def save_cache(ids):
    CACHE_FILE.write_text(json.dumps(list(ids)))

def fetch_url(url):
    """Fetch URL with rate limiting."""
    time.sleep(SLEEP_BETWEEN)
    req = urllib.request.Request(url, headers={"User-Agent": "ForgedByFreedom/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")

def search_pubmed(query, max_results=100):
    """Search PubMed and return article IDs."""
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance"
    })
    url = f"{NCBI_BASE}/esearch.fcgi?{params}"
    data = json.loads(fetch_url(url))
    return data.get("esearchresult", {}).get("idlist", [])

def fetch_abstracts(ids):
    """Fetch abstracts for given PubMed IDs."""
    if not ids:
        return []

    params = urllib.parse.urlencode({
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
        "rettype": "abstract"
    })
    url = f"{NCBI_BASE}/efetch.fcgi?{params}"
    xml = fetch_url(url)

    # Parse XML (simple regex extraction)
    articles = []

    # Extract each article
    for article_match in re.finditer(r'<PubmedArticle>(.*?)</PubmedArticle>', xml, re.DOTALL):
        article_xml = article_match.group(1)

        # Extract fields
        pmid = re.search(r'<PMID[^>]*>(\d+)</PMID>', article_xml)
        title = re.search(r'<ArticleTitle>(.+?)</ArticleTitle>', article_xml, re.DOTALL)
        abstract = re.search(r'<AbstractText[^>]*>(.+?)</AbstractText>', article_xml, re.DOTALL)
        journal = re.search(r'<Title>(.+?)</Title>', article_xml)
        year = re.search(r'<Year>(\d{4})</Year>', article_xml)

        # Get authors
        authors = re.findall(r'<LastName>(.+?)</LastName>', article_xml)

        if pmid and title:
            articles.append({
                "pmid": pmid.group(1),
                "title": clean_text(title.group(1)),
                "abstract": clean_text(abstract.group(1)) if abstract else "",
                "journal": clean_text(journal.group(1)) if journal else "",
                "year": year.group(1) if year else "",
                "authors": authors[:5]  # First 5 authors
            })

    return articles

def clean_text(text):
    """Clean XML/HTML from text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def save_article(article, topic):
    """Save article as text file."""
    filename = f"PMID{article['pmid']} - {article['title'][:80]}.txt"
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)  # Remove invalid chars
    filepath = OUTPUT_DIR / filename

    authors_str = ", ".join(article["authors"]) if article["authors"] else "Unknown"

    content = f"""PUBMED RESEARCH ABSTRACT
========================
PMID: {article['pmid']}
Title: {article['title']}
Authors: {authors_str}
Journal: {article['journal']}
Year: {article['year']}
Topic: {topic}

ABSTRACT:
{article['abstract']}

---
Source: https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/
"""

    filepath.write_text(content, encoding="utf-8")
    return filepath

# ─── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Fetch PubMed abstracts")
    parser.add_argument("--topic", help="Fetch specific topic only")
    parser.add_argument("--max", type=int, default=MAX_PER_TOPIC, help="Max results per topic")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fetched")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Add channel.url for pipeline
    channel_url = OUTPUT_DIR / "channel.url"
    if not channel_url.exists():
        channel_url.write_text("https://pubmed.ncbi.nlm.nih.gov/")

    fetched_ids = load_cache()
    topics = [args.topic] if args.topic else TOPICS

    print(f"\n{'='*60}")
    print("PUBMED RESEARCH FETCHER")
    print(f"{'='*60}")
    print(f"Topics: {len(topics)}")
    print(f"Max per topic: {args.max}")
    print(f"Already fetched: {len(fetched_ids)}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    total_new = 0

    for i, topic in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}] {topic}")

        try:
            # Search
            ids = search_pubmed(topic, args.max)
            new_ids = [id for id in ids if id not in fetched_ids]

            if args.dry_run:
                print(f"  Would fetch {len(new_ids)} new articles")
                continue

            if not new_ids:
                print(f"  No new articles")
                continue

            # Fetch in batches of 50
            for batch_start in range(0, len(new_ids), 50):
                batch = new_ids[batch_start:batch_start + 50]
                articles = fetch_abstracts(batch)

                for article in articles:
                    if article["abstract"]:  # Only save if has abstract
                        save_article(article, topic)
                        fetched_ids.add(article["pmid"])
                        total_new += 1

            print(f"  ✓ Fetched {len(new_ids)} articles")

        except Exception as e:
            print(f"  ✗ Error: {e}")

        # Save cache periodically
        if i % 10 == 0:
            save_cache(fetched_ids)

    save_cache(fetched_ids)

    print(f"\n{'='*60}")
    print(f"COMPLETE: {total_new} new articles fetched")
    print(f"Total cached: {len(fetched_ids)}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
