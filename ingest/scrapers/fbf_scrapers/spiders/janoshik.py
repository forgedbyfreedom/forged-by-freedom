"""
Janoshik Analytical Spider
Scrapes public.janoshik.com (browse all public tests) and individual
verify.janoshik.com/tests/{id} certificate pages.

Extracts every possible structured field for maximum searchability:
  - SQLite database (reports.sqlite) — SQL queries by any field
  - JSONL (reports.jsonl) — streaming / pandas analysis
  - JSON indices by verify_key / compound / vendor
  - .txt per report — Chroma RAG ingest
"""

import re
import json
from datetime import date
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

from fbf_scrapers.items import JanoshikReportItem

PUBLIC_BASE = "https://public.janoshik.com"
VERIFY_BASE = "https://verify.janoshik.com"

# Known verify keys from FBF vendor intelligence — seed these directly
KNOWN_VERIFY_KEYS = [
    # WWB compounds (from FBF research)
    "JWYYSCMQLK3X",   # WWB Anavar 25mg (Hepius) — Jan 2026
    "P371WNBS8Z4A",   # XT Labs Testoplex C300 — 193 mg/ml
    "9ED2J4XUFXJC",   # XT Labs Testoplex C300 — 203 mg/ml
    "57YX5ZX22G2M",   # Zhuoyue Retatrutide Apr 2026
    # WWB Sustanon Project Clear Gear
    "7Z22UPL4HMJ8",
    "C3NEZY7S9AS8",
    "5Y1E67G9TECI",
    # WWB AAS blind tests
    "2W_MR4VRFFK97BQ",
    "3W_E6NKZE2LX2QC",
    "4W_3KYXGA6MBISY",
    # Epithalon
    "1PKRQ7P4DIHG",
]

# ─── Compound normalization map ───────────────────────────────────────────────
NORMALIZE = {
    r"testosterone.?cypionate|test.?cyp|tc\b": "testosterone cypionate",
    r"testosterone.?enanthate|test.?enan|te\b": "testosterone enanthate",
    r"testosterone.?propionate|test.?prop|tp\b": "testosterone propionate",
    r"sustanon|sust\b|sus\b": "sustanon",
    r"nandrolone.?decanoate|deca.?durabolin|deca\b": "nandrolone decanoate",
    r"nandrolone.?phenylpropionate|npp\b": "nandrolone phenylpropionate",
    r"trenbolone.?acetate|tren.?ace|tren.?a\b": "trenbolone acetate",
    r"trenbolone.?enanthate|tren.?e\b": "trenbolone enanthate",
    r"boldenone.?undecylenate|equipoise|eq\b": "boldenone undecylenate",
    r"methenolone.?enanthate|primobolan.?depot|primo\b": "methenolone enanthate",
    r"drostanolone.?propionate|masteron.?prop|mast.?p\b": "drostanolone propionate",
    r"drostanolone.?enanthate|masteron.?enan|mast.?e\b": "drostanolone enanthate",
    r"oxandrolone|anavar\b": "oxandrolone",
    r"stanozolol|winstrol\b": "stanozolol",
    r"methandrostenolone|dianabol|dbol\b": "methandrostenolone",
    r"oxymetholone|anadrol\b": "oxymetholone",
    r"retatrutide|reta\b": "retatrutide",
    r"semaglutide|sema\b|ozempic|wegovy": "semaglutide",
    r"tirzepatide|tirze\b|mounjaro": "tirzepatide",
    r"bpc.?157": "bpc-157",
    r"tb.?500|thymosin.?beta": "tb-500",
    r"ghk.?cu|copper.?peptide": "ghk-cu",
    r"mots.?c\b": "mots-c",
    r"epithalon|epitalon": "epithalon",
    r"ipamorelin": "ipamorelin",
    r"cjc.?1295": "cjc-1295",
    r"tesamorelin": "tesamorelin",
    r"sermorelin": "sermorelin",
    r"igf.?1": "igf-1",
    r"hgh|somatropin|growth.?hormone": "somatropin (HGH)",
    r"5.amino.1.mq|5amino1mq": "5-amino-1mq",
    r"slu.?pp.?332": "slu-pp-332",
    r"tesofensine": "tesofensine",
    r"anastrozole|arimidex": "anastrozole",
    r"exemestane|aromasin": "exemestane",
    r"letrozole|femara": "letrozole",
    r"tamoxifen|nolvadex": "tamoxifen",
    r"clomiphene|clomid": "clomiphene",
    r"cabergoline|caber\b|dostinex": "cabergoline",
}

CATEGORY_MAP = {
    "testosterone cypionate": "AAS", "testosterone enanthate": "AAS",
    "testosterone propionate": "AAS", "sustanon": "AAS",
    "nandrolone decanoate": "AAS", "nandrolone phenylpropionate": "AAS",
    "trenbolone acetate": "AAS", "trenbolone enanthate": "AAS",
    "boldenone undecylenate": "AAS", "methenolone enanthate": "AAS",
    "drostanolone propionate": "AAS", "drostanolone enanthate": "AAS",
    "oxandrolone": "AAS", "stanozolol": "AAS",
    "methandrostenolone": "AAS", "oxymetholone": "AAS",
    "retatrutide": "GLP-1", "semaglutide": "GLP-1", "tirzepatide": "GLP-1",
    "bpc-157": "peptide", "tb-500": "peptide", "ghk-cu": "peptide",
    "mots-c": "peptide", "epithalon": "peptide", "ipamorelin": "peptide",
    "cjc-1295": "peptide", "tesamorelin": "peptide", "sermorelin": "peptide",
    "igf-1": "peptide", "somatropin (hgh)": "HGH",
    "5-amino-1mq": "novel", "slu-pp-332": "novel", "tesofensine": "novel",
    "anastrozole": "ancillary", "exemestane": "ancillary", "letrozole": "ancillary",
    "tamoxifen": "ancillary", "clomiphene": "ancillary", "cabergoline": "ancillary",
}

METHODS_KEYWORDS = [
    "HPLC-DAD", "HPLC", "LC-MS", "LCMS", "LC/MS", "GC-MS", "GCMS", "GC/MS",
    "MS/MS", "NMR", "ICP-MS", "EDX", "UV-Vis", "SIMEC", "Anabolic Lab",
]


def _normalize_compound(raw: str) -> str:
    raw_lower = raw.lower()
    for pattern, normalized in NORMALIZE.items():
        if re.search(pattern, raw_lower):
            return normalized
    return raw_lower.strip()


def _categorize(normalized: str) -> str:
    return CATEGORY_MAP.get(normalized.lower(), "unknown")


def _extract_methods(text: str) -> list:
    found = []
    for method in METHODS_KEYWORDS:
        if method.upper() in text.upper() or method.lower() in text.lower():
            if method not in found:
                found.append(method)
    return found


def _extract_amount_unit(text: str):
    """Extract numeric amount and unit from a result/label string."""
    m = re.search(r"([\d]+\.?\d*)\s*(mg/ml|mg/mL|mg/vial|mg/tab|mg|IU/vial|IU|%|mcg)", text, re.I)
    if m:
        return float(m.group(1)), m.group(2).lower()
    return None, None


def _purity_and_pass(label_amt, result_amt):
    if label_amt and result_amt and label_amt > 0:
        pct = (result_amt / label_amt) * 100
        if pct >= 95:
            pf = "pass"
        elif pct >= 85:
            pf = "marginal"
        else:
            pf = "fail"
        return round(pct, 2), pf
    return None, "unknown"


def _clean(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    deduped, prev = [], ""
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line
    return "\n".join(deduped)


class JanoshikSpider(scrapy.Spider):
    name = "janoshik"
    allowed_domains = ["public.janoshik.com", "verify.janoshik.com"]
    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        # Hard cap so a downed WAF doesn't block the rest of the nightly pipeline
        "CLOSESPIDER_TIMEOUT": 900,   # bail after 15 min if subdomains are down
    }

    def start_requests(self):
        # 1. Browse the public database
        yield scrapy.Request(f"{PUBLIC_BASE}/", callback=self.parse_public_listing)

        # 2. Seed known verify keys directly
        for key in KNOWN_VERIFY_KEYS:
            # Try both URL patterns Janoshik uses
            url = f"{VERIFY_BASE}/tests/{key}"
            yield scrapy.Request(url, callback=self.parse_verify_page,
                                 meta={"verify_key": key}, dont_filter=False)

    # ── Public listing: discover all public test pages ─────────────────────────
    def parse_public_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")

        # Find links to individual test pages (href pattern: /tests/{id} or similar)
        for a in soup.find_all("a", href=re.compile(r"/tests/|/test/")):
            href = a.get("href", "")
            full_url = urljoin(PUBLIC_BASE, href)
            # Extract verify key — Janoshik appends it after last _ or - separator
            m = re.search(r"[-_]([A-Z0-9]{8,})(?:/.*)?$", full_url, re.I)
            key = m.group(1).upper() if m else None
            yield scrapy.Request(full_url, callback=self.parse_verify_page,
                                 meta={"verify_key": key})

        # Paginate
        for a in soup.find_all("a", href=re.compile(r"[?&]page=\d+|/page/\d+")):
            next_url = urljoin(response.url, a.get("href", ""))
            if next_url != response.url:
                yield scrapy.Request(next_url, callback=self.parse_public_listing)

    # ── Individual verify page: extract all structured fields ─────────────────
    def parse_verify_page(self, response):
        if response.status != 200:
            return
        # Skip navigation/utility pages that are not real test certificates
        url_path = response.url.split("?")[0].rstrip("/")
        if re.search(r"/(navigation|sitemap|robots|login|wp-|feed|xmlrpc)", url_path, re.I):
            return
        # Must have a numeric test ID in the path
        if "tests" in url_path and not re.search(r"/tests/\d+", url_path):
            return

        raw_text = _clean(response.text)
        soup = BeautifulSoup(response.text, "html.parser")

        # Verify key — from meta, URL trailing segment, or page text
        verify_key = response.meta.get("verify_key")
        if not verify_key:
            m = re.search(r"[-_]([A-Z0-9]{8,})(?:/.*)?$", response.url, re.I)
            verify_key = m.group(1).upper() if m else None
        if not verify_key:
            m = re.search(r"\b([A-Z0-9]{10,16})\b", raw_text)
            verify_key = m.group(1) if m else None

        # ── Compound name ──────────────────────────────────────────────────────
        # Try structured fields first, then fall back to page title / heading
        compound_raw = ""
        for pattern in [
            r"[Cc]ompound[:\s]+([^\n]+)",
            r"[Ss]ubstance[:\s]+([^\n]+)",
            r"[Aa]nalyte[:\s]+([^\n]+)",
            r"[Pp]roduct[:\s]+([^\n]+)",
        ]:
            m = re.search(pattern, raw_text)
            if m:
                compound_raw = m.group(1).strip()
                break
        if not compound_raw:
            # Fall back to URL slug words (e.g. "Testosterone_Sustanon_250_KEYKEY")
            slug_part = response.url.rstrip("/").split("/")[-1]
            slug_part = re.sub(r"_?[A-Z0-9]{8,}$", "", slug_part)
            compound_raw = slug_part.replace("_", " ").replace("-", " ").strip()

        compound_normalized = _normalize_compound(compound_raw)
        compound_category = _categorize(compound_normalized)

        # ── Vendor / Manufacturer ──────────────────────────────────────────────
        vendor_raw = ""
        manufacturer_raw = ""
        for pattern in [
            (r"[Vv]endor[:\s]+([^\n]+)", "vendor"),
            (r"[Mm]anufacturer[:\s]+([^\n]+)", "mfr"),
            (r"[Ss]upplier[:\s]+([^\n]+)", "vendor"),
            (r"[Ss]ource[:\s]+([^\n]+)", "vendor"),
            (r"[Ss]ubmitted\s+by[:\s]+([^\n]+)", "vendor"),
        ]:
            m = re.search(pattern[0], raw_text)
            if m:
                val = m.group(1).strip()
                if pattern[1] == "vendor":
                    vendor_raw = vendor_raw or val
                else:
                    manufacturer_raw = manufacturer_raw or val

        # ── Batch number ───────────────────────────────────────────────────────
        batch_raw = ""
        m = re.search(r"[Bb]atch[:\s#]+([^\n]{2,30})", raw_text)
        if m:
            batch_raw = m.group(1).strip()

        # ── Label claim ───────────────────────────────────────────────────────
        label_str = ""
        for pattern in [
            r"[Ll]abel(?:ed)?[:\s]+([^\n]+(?:mg/ml|mg/mL|mg|IU|%)[^\n]*)",
            r"[Cc]laim(?:ed)?[:\s]+([^\n]+)",
            r"[Nn]ominal[:\s]+([^\n]+)",
            r"[Ll]abeled\s+amount[:\s]+([^\n]+)",
        ]:
            m = re.search(pattern, raw_text, re.I)
            if m:
                label_str = m.group(1).strip()
                break
        label_amount, label_unit = _extract_amount_unit(label_str)

        # ── Result ─────────────────────────────────────────────────────────────
        result_str = ""
        for pattern in [
            r"[Rr]esult[:\s]+([^\n]+(?:mg/ml|mg/mL|mg|IU|%)[^\n]*)",
            r"[Ff]ound[:\s]+([^\n]+)",
            r"[Aa]ctual[:\s]+([^\n]+)",
            r"[Mm]easured[:\s]+([^\n]+)",
            r"[Cc]ontent[:\s]+([^\n]+(?:mg|IU|%)[^\n]*)",
            # Pattern: "X.XX mg/ml" standalone
            r"([\d]+\.?\d+\s*(?:mg/ml|mg/mL|mg/vial|mg/tab|IU/vial|IU))",
        ]:
            m = re.search(pattern, raw_text, re.I)
            if m:
                result_str = m.group(1).strip()
                break
        result_amount, result_unit = _extract_amount_unit(result_str)

        # ── Purity percent (may also be stated directly) ───────────────────────
        purity_pct = None
        m = re.search(r"[Pp]urity[:\s]+([\d]+\.?\d+)\s*%", raw_text)
        if m:
            purity_pct = float(m.group(1))
        if purity_pct is None:
            purity_pct, _ = _purity_and_pass(label_amount, result_amount)
        _, pass_fail = _purity_and_pass(label_amount, result_amount)
        if purity_pct and pass_fail == "unknown":
            if purity_pct >= 95:
                pass_fail = "pass"
            elif purity_pct >= 85:
                pass_fail = "marginal"
            else:
                pass_fail = "fail"

        # ── Compound present / unexpected compounds ───────────────────────────
        compound_present = None
        unexpected = []
        text_lower = raw_text.lower()
        if any(w in text_lower for w in ["not detected", "not found", "absent", "no compound"]):
            compound_present = False
            pass_fail = "fail"
        elif any(w in text_lower for w in ["detected", "confirmed", "identified", "present"]):
            compound_present = True
        unexpected_patterns = re.findall(
            r"(?:unexpected|unknown|additional|foreign)\s+(?:compound|substance)[:\s]+([^\n.]+)",
            raw_text, re.I)
        if unexpected_patterns:
            unexpected = [p.strip() for p in unexpected_patterns]

        # ── Methods ────────────────────────────────────────────────────────────
        methods = _extract_methods(raw_text)

        # ── Heavy metals ───────────────────────────────────────────────────────
        heavy_tested = bool(re.search(r"heavy.?metal|EDX|ICP|arsenic|lead|mercury|cadmium", raw_text, re.I))
        heavy_pass = None
        if heavy_tested:
            if re.search(r"heavy.?metal[s]?\s*[:\-]\s*pass|metals.*not detected", raw_text, re.I):
                heavy_pass = True
            elif re.search(r"heavy.?metal[s]?\s*[:\-]\s*fail|metals.*detected", raw_text, re.I):
                heavy_pass = False

        # ── Date ───────────────────────────────────────────────────────────────
        test_date = ""
        for pattern in [
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{1,2}\s+\w+\s+\d{4})",
            r"(\w+\s+\d{1,2},?\s+\d{4})",
        ]:
            m = re.search(pattern, raw_text)
            if m:
                test_date = m.group(1)
                if re.match(r"\d{4}-\d{2}-\d{2}", test_date):
                    break

        # ── Submitter type ─────────────────────────────────────────────────────
        submitter_type = "unknown"
        if re.search(r"blind\s+test|community\s+test|independent\s+test", raw_text, re.I):
            submitter_type = "blind_test"
        elif re.search(r"manufacturer|self.?submit|lab\s+submitt", raw_text, re.I):
            submitter_type = "manufacturer"
        elif re.search(r"community|member|user\s+submit|buyer", raw_text, re.I):
            submitter_type = "community"

        yield JanoshikReportItem(
            verify_key=verify_key,
            verify_url=response.url,
            compound_raw=compound_raw,
            compound_normalized=compound_normalized,
            compound_category=compound_category,
            vendor_raw=vendor_raw,
            manufacturer_raw=manufacturer_raw,
            batch_number=batch_raw,
            submitter_type=submitter_type,
            label_amount=label_amount,
            label_unit=label_unit,
            label_concentration=label_str or None,
            result_amount=result_amount,
            result_unit=result_unit or label_unit,
            result_raw=result_str or None,
            purity_percent=purity_pct,
            pass_fail=pass_fail,
            compound_present=compound_present,
            unexpected_compounds=unexpected,
            methods=methods,
            heavy_metals_tested=heavy_tested if heavy_tested else None,
            heavy_metals_pass=heavy_pass,
            test_date=test_date,
            scraped_date=date.today().isoformat(),
            raw_text=raw_text,
        )
