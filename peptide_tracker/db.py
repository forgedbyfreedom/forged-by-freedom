"""SQLite layer for the peptide tracker.

Storage: ~/.peptide_tracker/inventory.db (created automatically).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional


DB_DIR = Path(os.path.expanduser("~/.peptide_tracker"))
DB_PATH = DB_DIR / "inventory.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS peptides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  amount_per_vial REAL,
  units TEXT NOT NULL DEFAULT 'mg',           -- 'mg' or 'IU'
  vial_count INTEGER NOT NULL DEFAULT 1,
  reconstituted INTEGER NOT NULL DEFAULT 0,   -- bool: 0 = powder, 1 = mixed
  reconstitution_date TEXT,                   -- ISO YYYY-MM-DD
  bac_water_ml REAL,
  expiration_date TEXT,                       -- ISO YYYY-MM-DD
  vendor TEXT,
  batch TEXT,
  coa_code TEXT,
  cost REAL,
  storage TEXT NOT NULL DEFAULT 'freezer',    -- 'freezer' | 'fridge' | 'room'
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_peptides_name ON peptides(name);
CREATE INDEX IF NOT EXISTS idx_peptides_expiration ON peptides(expiration_date);
"""


COLUMNS = [
    "name", "amount_per_vial", "units", "vial_count",
    "reconstituted", "reconstitution_date", "bac_water_ml",
    "expiration_date", "vendor", "batch", "coa_code", "cost",
    "storage", "notes",
]


def get_conn() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as c:
        c.executescript(SCHEMA)


def list_all(search: str = "") -> list[dict]:
    sql = "SELECT * FROM peptides"
    params: tuple = ()
    if search:
        sql += " WHERE name LIKE ? OR vendor LIKE ? OR batch LIKE ? OR notes LIKE ?"
        like = f"%{search}%"
        params = (like, like, like, like)
    sql += " ORDER BY name COLLATE NOCASE"
    with get_conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_with_status(dict(r)) for r in rows]


def get(item_id: int) -> Optional[dict]:
    with get_conn() as c:
        row = c.execute("SELECT * FROM peptides WHERE id = ?", (item_id,)).fetchone()
    return _with_status(dict(row)) if row else None


def create(data: dict) -> int:
    clean = _sanitize(data)
    cols = [k for k in COLUMNS if k in clean]
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO peptides ({', '.join(cols)}) VALUES ({placeholders})"
    with get_conn() as c:
        cur = c.execute(sql, tuple(clean[k] for k in cols))
        return int(cur.lastrowid)


def update(item_id: int, data: dict) -> int:
    clean = _sanitize(data)
    cols = [k for k in COLUMNS if k in clean]
    if not cols:
        return 0
    sets = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = datetime('now')"
    sql = f"UPDATE peptides SET {sets} WHERE id = ?"
    with get_conn() as c:
        cur = c.execute(sql, (*[clean[k] for k in cols], item_id))
        return cur.rowcount


def delete(item_id: int) -> int:
    with get_conn() as c:
        cur = c.execute("DELETE FROM peptides WHERE id = ?", (item_id,))
        return cur.rowcount


# ── helpers ───────────────────────────────────────────────────────────
def _sanitize(data: dict) -> dict:
    """Pick known fields, coerce types, drop empties to NULL."""
    out = {}
    for k in COLUMNS:
        if k not in data:
            continue
        v = data[k]
        if v is None or v == "":
            out[k] = None
            continue
        if k in ("amount_per_vial", "bac_water_ml", "cost"):
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                out[k] = None
        elif k == "vial_count":
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                out[k] = 0
        elif k == "reconstituted":
            out[k] = 1 if v in (True, 1, "1", "true", "True", "on", "yes") else 0
        else:
            out[k] = str(v).strip()
    return out


def _with_status(row: dict) -> dict:
    """Attach computed status fields for the dashboard."""
    today = date.today()
    status = "ok"
    status_note = ""
    days_since_recon = None
    days_to_expiry = None

    if row.get("reconstituted") and row.get("reconstitution_date"):
        try:
            rd = date.fromisoformat(row["reconstitution_date"])
            days_since_recon = (today - rd).days
            if days_since_recon > 28:
                status = "expired"
                status_note = f"reconstituted {days_since_recon}d ago — likely degraded"
            elif days_since_recon > 21:
                status = "warn"
                status_note = f"reconstituted {days_since_recon}d ago — use soon"
            else:
                status_note = f"reconstituted {days_since_recon}d ago"
        except ValueError:
            pass

    if row.get("expiration_date"):
        try:
            ed = date.fromisoformat(row["expiration_date"])
            days_to_expiry = (ed - today).days
            if days_to_expiry < 0:
                status = "expired"
                status_note = (status_note + " · " if status_note else "") + \
                              f"expired {-days_to_expiry}d ago"
            elif days_to_expiry < 30 and status != "expired":
                if status != "warn":
                    status = "warn"
                status_note = (status_note + " · " if status_note else "") + \
                              f"expires in {days_to_expiry}d"
        except ValueError:
            pass

    row["status"] = status
    row["status_note"] = status_note
    row["days_since_recon"] = days_since_recon
    row["days_to_expiry"] = days_to_expiry
    return row
