#!/usr/bin/env python3
"""
FBF Reddit Scraper — no credentials required.
Primary: Arctic Shift API (arctic-shift.photon-reddit.com) — historical archive, free, no auth.
Comments: old.reddit.com HTML for high-score posts only.

Usage:
  python reddit_scraper.py                      # all subreddits
  python reddit_scraper.py --sub steroids       # single subreddit
  python reddit_scraper.py --sub peptides --days 180  # last 180 days only
"""

import argparse
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent.parent  # forged-by-freedom/
CHANNELS_DIR = BASE_DIR / "ingest" / "channels"

SUBREDDITS = [
    "steroids",
    "peptides",
    "sarmssourcetalk",
    "anabolics",
    "retatrutide",
    "GLP1",
    "GLP",
    "fitness",
    "weightloss",
    "roids",
]

POSTS_PER_BATCH  = 100      # Arctic Shift max per request
MAX_POSTS        = 500      # per subreddit cap
COMMENT_LIMIT    = 20       # top comments to fetch
MIN_SCORE        = 2        # skip only junk (score 0-1)
COMMENT_SCORE_THRESHOLD = 25  # only fetch comments for posts with score >= this
DAYS_BACK        = 3650     # 10 years

ARCTIC_POST_URL    = "https://arctic-shift.photon-reddit.com/api/posts/search"
ARCTIC_COMMENT_URL = "https://arctic-shift.photon-reddit.com/api/comments/search"
OLD_REDDIT_BASE    = "https://old.reddit.com"

HEADERS = {"User-Agent": "FBF-RAG-Scraper/1.0 (research; contact forgedbyfreedom@gmail.com)"}


def _get(url: str, params: dict = None) -> dict | None:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json()
        print(f"  HTTP {r.status_code}: {url}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def _get_html(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        return None
    except Exception:
        return None


def clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slug(text: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    s = re.sub(r"[\s_-]+", "_", s).strip("_")
    return s[:maxlen]


def fetch_comments_arctic(post_id: str) -> list[str]:
    data = _get(ARCTIC_COMMENT_URL, {"link_id": f"t3_{post_id}", "limit": COMMENT_LIMIT})
    time.sleep(0.6)
    if not data:
        return []
    comments = []
    for c in data.get("data", []):
        body = clean(c.get("body", ""))
        if body and body not in ("[deleted]", "[removed]"):
            comments.append(body)
    return comments


def fetch_comments_oldreddit(permalink: str) -> list[str]:
    url = f"{OLD_REDDIT_BASE}{permalink}?sort=top&limit=50"
    soup = _get_html(url)
    if not soup:
        return []
    time.sleep(1.5)
    comments = []
    for div in soup.find_all("div", class_=re.compile(r"\bmd\b")):
        parent = div.find_parent("div", class_=re.compile(r"comment"))
        if not parent:
            continue
        if parent.get("data-depth", "0") not in ("0", "1"):
            continue
        text = clean(div.get_text(separator="\n"))
        if text and len(text) > 10:
            comments.append(text)
            if len(comments) >= COMMENT_LIMIT:
                break
    return comments


def post_to_txt(post: dict, comments: list[str], subreddit: str) -> str:
    dt = datetime.fromtimestamp(
        post.get("created_utc", 0), tz=timezone.utc).date().isoformat()
    author = post.get("author", "[deleted]")
    flair = post.get("link_flair_text", "") or ""
    selftext = clean(post.get("selftext", "") or "[link post]")

    lines = [
        f"Source: Reddit r/{subreddit}",
        f"Title: {post.get('title', '')}",
        f"URL: https://www.reddit.com{post.get('permalink', '')}",
        f"Author: u/{author}",
        f"Date: {dt}",
        f"Score: {post.get('score', 0)}",
    ]
    if flair:
        lines.append(f"Flair: {flair}")
    lines += [
        f"Speaker: Reddit u/{author}",
        "=" * 60,
        "",
        f"POST:\n{selftext}",
        "",
        "COMMENTS:",
    ]
    for i, c in enumerate(comments, 1):
        lines.append(f"\n[Comment {i}]\n{c}")
    return "\n".join(lines)


def scrape_subreddit(sub_name: str, days_back: int) -> int:
    out_dir = CHANNELS_DIR / f"@Reddit_{sub_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
    before = None   # paginate backwards from now
    saved = 0
    total_fetched = 0

    print(f"  r/{sub_name} — fetching up to {MAX_POSTS} posts (last {days_back} days)")

    while total_fetched < MAX_POSTS:
        params = {
            "subreddit": sub_name,
            "limit":     POSTS_PER_BATCH,
            "sort":      "desc",
        }
        if before:
            params["before"] = before

        data = _get(ARCTIC_POST_URL, params)
        time.sleep(1)
        if not data:
            break

        posts = data.get("data", [])
        if not posts:
            break

        for post in posts:
            ts = post.get("created_utc", 0)
            if ts < cutoff:
                return saved  # past our cutoff — stop

            total_fetched += 1
            score = post.get("score", 0)

            if score < MIN_SCORE:
                continue
            if post.get("selftext", "") in ("[removed]", "[deleted]", "", None) \
               and score < 20:
                continue  # link post with low score — skip

            pid = post.get("id", "")
            out_file = out_dir / f"{pid}_{slug(post.get('title', ''))}.txt"
            if out_file.exists():
                continue

            # Fetch comments — pullpush first, old.reddit fallback for high scorers
            comments = []
            if score >= COMMENT_SCORE_THRESHOLD:
                comments = fetch_comments_arctic(pid)
                if not comments and post.get("permalink"):
                    comments = fetch_comments_oldreddit(post["permalink"])

            content = post_to_txt(post, comments, sub_name)
            out_file.write_text(content, encoding="utf-8")
            saved += 1

        # Next page — use the oldest timestamp in this batch
        before = int(posts[-1].get("created_utc", 0))
        if before < cutoff:
            break

    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sub",  help="Single subreddit (without r/)")
    parser.add_argument("--days", type=int, default=DAYS_BACK,
                        help=f"Days of history to fetch (default {DAYS_BACK})")
    args = parser.parse_args()

    subs = [args.sub] if args.sub else SUBREDDITS

    print("=" * 60)
    print("  FBF REDDIT SCRAPER (Arctic Shift)")
    print(f"  Subreddits : {', '.join(subs)}")
    print(f"  History    : {args.days} days")
    print("=" * 60)

    total = 0
    for sub in subs:
        print(f"\nr/{sub}")
        n = scrape_subreddit(sub, args.days)
        print(f"  {n} posts saved")
        total += n
        time.sleep(2)

    print(f"\nDone — {total} total posts saved to {CHANNELS_DIR}")


if __name__ == "__main__":
    main()
