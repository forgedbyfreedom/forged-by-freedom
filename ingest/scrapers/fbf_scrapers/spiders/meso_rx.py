"""
MESO-Rx Vendor Thread Spider
Crawls thinksteroids.com/community vendor/source threads only.
Paginates through all pages of each thread and extracts every post.
"""

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import scrapy
from bs4 import BeautifulSoup

from fbf_scrapers.items import ForumPostItem

# ─── Seed: known vendor threads from FBF intelligence research ────────────────
SEED_VENDOR_THREADS = [
    # WWB (Wuhan Wansheng)
    "https://thinksteroids.com/community/threads/wuhan-wansheng-biotechnology-co-ltd-usa-international.134426504/",
    "https://thinksteroids.com/community/threads/project-clear-gear-wwb-wuhan-wansheng-biotechnology-sustanon-250-blind-testing-heavy-metals-gcms-lcms-janoshik-analytical-nov2025.134433612/",
    "https://thinksteroids.com/community/threads/wwb-blind-janoshik-testing.134434027/",
    "https://thinksteroids.com/community/threads/wwb-100-iu-hgh-kit-testing.134433552/",
    "https://thinksteroids.com/community/threads/warning-scammed-twice-by-chinese-peptide-vendors-fake-sources-pretending-to-be-wuhan-wansheng-bio-laikang-biotechnology.134437666/",
    # Zhuoyue (Reta source)
    "https://thinksteroids.com/community/threads/zhuoyue-biotechnology-official-thread.134420000/",
    # Project Clear Gear (blind testing)
    "https://thinksteroids.com/community/threads/project-clear-gear-collab-ppd-tc-raws-blind-testing-janoshik-analytical-apr2026.134440317/",
    # QSC
    "https://thinksteroids.com/community/threads/qsc-peptides.134425000/",
    # HYB / Hangzhou Youngpeptide
    "https://thinksteroids.com/community/threads/hyb-hangzhou-youngpeptide.134424000/",
    # Pharmacom
    "https://thinksteroids.com/community/threads/pharmacom-labs-official-thread.134350000/",
    # Ascension Peptides
    "https://thinksteroids.com/community/threads/ascension-peptides.134430000/",
    # Peptide Partners
    "https://thinksteroids.com/community/threads/peptide-partners-official.134415000/",
]

# ─── Forum sections to discover additional vendor threads ─────────────────────
SEED_FORUMS = [
    "https://thinksteroids.com/community/forums/underground-labs.133/",
    "https://thinksteroids.com/community/forums/peptide-underground.142/",
    "https://thinksteroids.com/community/forums/anabolic-steroid-discussion.134/",
    "https://thinksteroids.com/community/forums/source-checks.135/",
    "https://thinksteroids.com/community/forums/steroid-underground.136/",
]

DOMAIN = "thinksteroids.com"


def _extract_thread_id(url: str) -> str:
    m = re.search(r"\.(\d+)/?$", url.rstrip("/").split("page-")[0])
    return m.group(1) if m else "unknown"


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "aside", "form"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and len(l) > 2]
    deduped, prev = [], ""
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line
    return "\n".join(deduped)


def _parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%b %d, %Y at %I:%M %p", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    # XenForo often uses relative dates in attributes — return raw if unparseable
    return raw[:20] if raw else ""


class MesoRxVendorSpider(scrapy.Spider):
    name = "meso_rx"
    allowed_domains = [DOMAIN]
    custom_settings = {
        "DOWNLOAD_DELAY": 3.0,
        "COMPRESSION_ENABLED": False,  # thinksteroids.com returns HTML not gzip despite header
    }

    def start_requests(self):
        # Seed with known vendor threads
        for url in SEED_VENDOR_THREADS:
            yield scrapy.Request(url, callback=self.parse_thread,
                                 meta={"thread_url": url, "page": 1})
        # Discover more from forum listing pages
        for url in SEED_FORUMS:
            yield scrapy.Request(url, callback=self.parse_forum_listing)

    # ── Forum listing: find thread links ──────────────────────────────────────
    def parse_forum_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")

        # XenForo thread link pattern: <a href="/community/threads/...">
        for a in soup.find_all("a", href=re.compile(r"/community/threads/")):
            href = a.get("href", "")
            if not href:
                continue
            full_url = urljoin(response.url, href)
            # Strip page anchors — only first page needed to start
            full_url = re.sub(r"/page-\d+", "", full_url).rstrip("/") + "/"
            yield scrapy.Request(full_url, callback=self.parse_thread,
                                 meta={"thread_url": full_url, "page": 1},
                                 dont_filter=False)

        # Paginate the forum listing itself
        next_page = soup.find("a", class_=re.compile(r"pageNav-jump--next|next"))
        if next_page:
            next_url = urljoin(response.url, next_page.get("href", ""))
            if next_url != response.url:
                yield scrapy.Request(next_url, callback=self.parse_forum_listing)

    # ── Thread page: extract posts ────────────────────────────────────────────
    def parse_thread(self, response):
        thread_url = response.meta.get("thread_url", response.url)
        page_num = response.meta.get("page", 1)
        thread_id = _extract_thread_id(thread_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Thread title
        title_el = (soup.find("h1", class_=re.compile(r"p-title-value|thread-title")) or
                    soup.find("h1"))
        thread_title = title_el.get_text(strip=True) if title_el else "Unknown"

        # Posts — XenForo wraps each post in article[data-content] or div.message
        posts = (soup.find_all("article", attrs={"data-content": True}) or
                 soup.find_all("div", class_=re.compile(r"\bmessage\b")))

        for post in posts:
            # Author
            author_el = (post.find(class_=re.compile(r"message-name|username|author")) or
                         post.find(attrs={"data-author": True}))
            author = (author_el.get("data-author") or
                      (author_el.get_text(strip=True) if author_el else "unknown"))

            # Date — XenForo uses <time datetime="ISO">
            time_el = post.find("time")
            date_raw = time_el.get("datetime", time_el.get_text(strip=True)) if time_el else ""
            date_iso = date_raw[:10] if re.match(r"\d{4}-\d{2}-\d{2}", date_raw) else _parse_date(date_raw)

            # Post ID and number
            post_id = post.get("data-content", post.get("id", ""))
            post_num_el = post.find(class_=re.compile(r"message-attribution-opposite|post-number"))
            post_number = post_num_el.get_text(strip=True).lstrip("#") if post_num_el else ""

            # Content body
            body_el = (post.find(class_=re.compile(r"message-body|bbWrapper|post-content")) or
                       post.find("div", class_=re.compile(r"content")))
            content = _clean_text(str(body_el)) if body_el else _clean_text(str(post))

            if len(content) < 20:
                continue

            yield ForumPostItem(
                source="meso_rx",
                thread_id=thread_id,
                thread_title=thread_title,
                thread_url=thread_url,
                subforum="vendor_threads",
                post_id=post_id,
                post_number=post_number,
                author=author,
                date_raw=date_raw,
                date_iso=date_iso,
                content=content,
                page_num=page_num,
            )

        # ── Pagination: follow next page ──────────────────────────────────────
        next_el = soup.find("a", class_=re.compile(r"pageNav-jump--next"))
        if next_el:
            next_href = next_el.get("href", "")
            next_url = urljoin(response.url, next_href)
            # Update page number from URL
            page_match = re.search(r"page-(\d+)", next_url)
            next_page = int(page_match.group(1)) if page_match else page_num + 1
            yield scrapy.Request(next_url, callback=self.parse_thread,
                                 meta={"thread_url": thread_url, "page": next_page})
