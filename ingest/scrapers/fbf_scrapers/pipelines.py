import json
import sqlite3
import re
from datetime import date
from pathlib import Path

from fbf_scrapers.items import ForumPostItem, JanoshikReportItem

BASE_DIR = Path(__file__).parent.parent.parent.parent  # forged-by-freedom/
CHANNELS_DIR = BASE_DIR / "ingest" / "channels"
JANOSHIK_DB_DIR = BASE_DIR / "ingest" / "janoshik_db"


# ─── Text Output (all items → .txt files for Chroma ingest) ───────────────────

class TextOutputPipeline:

    def open_spider(self, spider):
        CHANNELS_DIR.mkdir(exist_ok=True)
        JANOSHIK_DB_DIR.mkdir(exist_ok=True)
        self._written: set[str] = set()  # in-memory dedup within a single run

    def process_item(self, item, spider):
        if isinstance(item, ForumPostItem):
            self._write_forum_post(item)
        elif isinstance(item, JanoshikReportItem):
            self._write_janoshik_txt(item)
        return item

    def _write_forum_post(self, item):
        out_dir = CHANNELS_DIR / f"@MesoRx_vendors"
        out_dir.mkdir(exist_ok=True)
        tid = item.get("thread_id", "unknown")
        pid = item.get("post_id", item.get("post_number", "0"))
        out_file = out_dir / f"thread_{tid}_post_{pid}.txt"
        if out_file.exists():
            return
        content = (
            f"Source: MESO-Rx Forum — Vendor Thread\n"
            f"Thread: {item.get('thread_title', '')}\n"
            f"URL: {item.get('thread_url', '')}\n"
            f"Author: {item.get('author', 'unknown')}\n"
            f"Date: {item.get('date_iso', item.get('date_raw', ''))}\n"
            f"Post #: {item.get('post_number', '')}\n"
            f"Speaker: MESO-Rx Community Member\n"
            "=" * 60 + "\n\n"
            f"{item.get('content', '')}"
        )
        out_file.write_text(content, encoding="utf-8")

    def _write_janoshik_txt(self, item):
        out_dir = CHANNELS_DIR / "@Janoshik"
        out_dir.mkdir(exist_ok=True)
        raw_key = item.get("verify_key") or item.get("verify_url", "unknown").split("/")[-1]
        key = re.sub(r"[^\w]", "_", raw_key or "unknown")
        if key in self._written:
            return
        out_file = out_dir / f"{key}.txt"
        if out_file.exists():
            self._written.add(key)
            return
        compound = item.get("compound_raw", "Unknown Compound")
        vendor = item.get("vendor_raw", "Unknown Vendor")
        purity = item.get("purity_percent")
        pct_str = f"{purity:.1f}%" if purity is not None else "N/A"
        result_raw = item.get("result_raw", "")
        label = item.get("label_concentration", "")
        methods = ", ".join(item.get("methods") or [])
        content = (
            f"Source: Janoshik Analytical — Test Certificate\n"
            f"Compound: {compound}\n"
            f"Vendor/Manufacturer: {vendor}\n"
            f"Verify Key: {item.get('verify_key', '')}\n"
            f"URL: {item.get('verify_url', '')}\n"
            f"Label Claim: {label}\n"
            f"Result: {result_raw}\n"
            f"Purity vs Label: {pct_str}\n"
            f"Pass/Fail: {item.get('pass_fail', 'unknown')}\n"
            f"Methods: {methods}\n"
            f"Test Date: {item.get('test_date', '')}\n"
            f"Speaker: Janoshik Analytical Laboratory\n"
            "=" * 60 + "\n\n"
            f"{item.get('raw_text', '')}"
        )
        out_file.write_text(content, encoding="utf-8")
        self._written.add(key)


# ─── Janoshik Structured Output (JSONL + SQLite + JSON indices) ───────────────

class JanoshikStructuredPipeline:

    def open_spider(self, spider):
        if not hasattr(spider, "name") or "janoshik" not in spider.name:
            return
        JANOSHIK_DB_DIR.mkdir(exist_ok=True)
        self.jsonl_path = JANOSHIK_DB_DIR / "reports.jsonl"
        self._init_sqlite()
        self._seen_keys = self._load_seen_keys()

    def _init_sqlite(self):
        self.db = sqlite3.connect(JANOSHIK_DB_DIR / "reports.sqlite")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS janoshik_reports (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                verify_key          TEXT UNIQUE,
                verify_url          TEXT,
                compound_raw        TEXT,
                compound_normalized TEXT,
                compound_category   TEXT,
                vendor_raw          TEXT,
                manufacturer_raw    TEXT,
                batch_number        TEXT,
                submitter_type      TEXT,
                label_amount        REAL,
                label_unit          TEXT,
                label_concentration TEXT,
                result_amount       REAL,
                result_unit         TEXT,
                result_raw          TEXT,
                purity_percent      REAL,
                pass_fail           TEXT,
                compound_present    INTEGER,
                unexpected_compounds TEXT,
                methods             TEXT,
                heavy_metals_tested INTEGER,
                heavy_metals_pass   INTEGER,
                test_date           TEXT,
                scraped_date        TEXT,
                raw_text            TEXT,
                source_url          TEXT
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_compound  ON janoshik_reports(compound_normalized)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_vendor    ON janoshik_reports(vendor_raw COLLATE NOCASE)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_purity    ON janoshik_reports(purity_percent)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_pass_fail ON janoshik_reports(pass_fail)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_category  ON janoshik_reports(compound_category)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_date      ON janoshik_reports(test_date)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_key       ON janoshik_reports(verify_key)")
        self.db.commit()

    def _load_seen_keys(self):
        cur = self.db.execute("SELECT verify_key FROM janoshik_reports")
        return {row[0] for row in cur.fetchall()}

    def process_item(self, item, spider):
        if not isinstance(item, JanoshikReportItem):
            return item
        key = item.get("verify_key")
        if key and key in self._seen_keys:
            return item
        self._write_sqlite(item)
        self._write_jsonl(item)
        if key:
            self._seen_keys.add(key)
        return item

    def _write_sqlite(self, item):
        methods = item.get("methods") or []
        unexpected = item.get("unexpected_compounds") or []
        self.db.execute("""
            INSERT OR IGNORE INTO janoshik_reports (
                verify_key, verify_url, compound_raw, compound_normalized,
                compound_category, vendor_raw, manufacturer_raw, batch_number,
                submitter_type, label_amount, label_unit, label_concentration,
                result_amount, result_unit, result_raw, purity_percent,
                pass_fail, compound_present, unexpected_compounds, methods,
                heavy_metals_tested, heavy_metals_pass, test_date,
                scraped_date, raw_text, source_url
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            item.get("verify_key"), item.get("verify_url"),
            item.get("compound_raw"), item.get("compound_normalized"),
            item.get("compound_category"), item.get("vendor_raw"),
            item.get("manufacturer_raw"), item.get("batch_number"),
            item.get("submitter_type"),
            item.get("label_amount"), item.get("label_unit"),
            item.get("label_concentration"),
            item.get("result_amount"), item.get("result_unit"),
            item.get("result_raw"), item.get("purity_percent"),
            item.get("pass_fail"),
            int(item["compound_present"]) if item.get("compound_present") is not None else None,
            json.dumps(unexpected),
            json.dumps(methods),
            int(item["heavy_metals_tested"]) if item.get("heavy_metals_tested") is not None else None,
            int(item["heavy_metals_pass"]) if item.get("heavy_metals_pass") is not None else None,
            item.get("test_date"), item.get("scraped_date"),
            item.get("raw_text"), item.get("verify_url"),
        ))
        self.db.commit()

    def _write_jsonl(self, item):
        row = {k: v for k, v in item.items() if v is not None}
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def close_spider(self, spider):
        if not hasattr(self, "db"):
            return
        self._rebuild_json_indices()
        self.db.close()

    def _rebuild_json_indices(self):
        cur = self.db.execute(
            "SELECT verify_key, compound_normalized, vendor_raw, purity_percent, "
            "pass_fail, test_date, label_concentration, result_raw, methods, compound_category "
            "FROM janoshik_reports"
        )
        by_key = {}
        by_compound = {}
        by_vendor = {}

        for row in cur.fetchall():
            key, compound, vendor, purity, pf, dt, label, result, methods_json, cat = row
            entry = {
                "verify_key": key, "compound": compound, "vendor": vendor,
                "purity_percent": purity, "pass_fail": pf, "test_date": dt,
                "label": label, "result": result,
                "methods": json.loads(methods_json) if methods_json else [],
                "category": cat,
            }
            if key:
                by_key[key] = entry
            if compound:
                by_compound.setdefault(compound, []).append(entry)
            if vendor:
                by_vendor.setdefault(vendor.lower(), []).append(entry)

        (JANOSHIK_DB_DIR / "index_by_verify_key.json").write_text(
            json.dumps(by_key, indent=2), encoding="utf-8")
        (JANOSHIK_DB_DIR / "index_by_compound.json").write_text(
            json.dumps(by_compound, indent=2), encoding="utf-8")
        (JANOSHIK_DB_DIR / "index_by_vendor.json").write_text(
            json.dumps(by_vendor, indent=2), encoding="utf-8")
