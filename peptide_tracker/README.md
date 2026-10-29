# Peptide Tracker 💉

A small local-only inventory dashboard for on-hand peptides. Tracks vials,
reconstitution dates, expirations, vendors, batches, COA codes, costs, and
storage location.

> ## What it is — and isn't
>
> A personal recordkeeping tool. **Local only** — data lives in
> `~/.peptide_tracker/inventory.db` on your machine. Nothing leaves the
> device. No cloud, no telemetry. Bind only to `127.0.0.1` unless you mean
> otherwise.
>
> It does not give medical or dosing advice. It does not replace a pharmacist
> or a physician. It assumes you already know what you're doing.

## Install + run

```bash
cd peptide_tracker
pip install -r requirements.txt
python -m peptide_tracker.app
# → http://127.0.0.1:5058
```

To bind to your LAN (so you can read inventory from your phone on the same
Wi-Fi), pass `--host 0.0.0.0 --port 5058`. **There is no authentication** —
anyone on your network can read and modify the inventory. Don't do this on a
network you don't control.

## What it tracks per item

| Field | Notes |
|---|---|
| Name | Required. e.g. "HGH 36iu", "BPC-157", "NAD+ 500mg". |
| Amount per vial · Units | Quantitative content. `mg` / `IU` / `mcg`. |
| Vial count | How many of this item you currently have. |
| Reconstituted? | If yes, captures the date and bac-water mL. |
| Reconstitution date | Used for the 21d/28d degradation warning. |
| Expiration date | Used for the 30d / overdue warning. |
| Vendor | e.g. "Shengyufan", "Toomey". |
| Batch / lot | What's printed on the vial. |
| COA verify code | Janoshik verification code, etc. |
| Cost | What you paid. |
| Storage | Freezer / Fridge / Room temp. |
| Notes | Anything else — dosing protocol, recent test result. |

## Status logic

The dashboard color-codes each row:

| State | Trigger | Action |
|---|---|---|
| **OK** (green) | Powder, or recently reconstituted, or far from expiration | none |
| **WARN** (yellow) | Reconstituted 21–28 days ago, OR expires within 30 days | use soon |
| **EXPIRED** (red) | Reconstituted > 28 days ago, OR past expiration date | likely degraded — discard |

The thresholds (21d / 28d / 30d) are reasonable defaults for many peptides
but vary by compound. HGH specifically holds ~28 days in the fridge after
reconstitution if handled cleanly; some others (e.g. GHRPs) are shorter.
Adjust by editing `db._with_status()` if you want different thresholds.

## Export + backup

Two one-click downloads in the header:

- **JSON** — full snapshot with timestamps, all fields, computed status notes.
- **CSV** — spreadsheet view with computed `days_since_recon` and
  `days_to_expiry` columns.

Both go to a date-stamped filename (`peptide-inventory-YYYYMMDD.json`).

The underlying SQLite file at `~/.peptide_tracker/inventory.db` is also safe
to copy/back-up directly.

## API

| Method + path | Purpose |
|---|---|
| `GET /api/items?q=…` | List items, optional search. |
| `POST /api/items` | Create. Body: JSON of the fields above. |
| `PUT /api/items/<id>` | Update. Body: partial JSON, only the fields you want to change. |
| `DELETE /api/items/<id>` | Delete. |
| `GET /api/export/json` | Download full snapshot. |
| `GET /api/export/csv` | Download CSV. |

## Storage layout

```
~/.peptide_tracker/
└── inventory.db   ← SQLite, single table 'peptides', autocreated on first run
```

The schema is in `peptide_tracker/db.py` (`SCHEMA` constant) and auto-creates
on first run. Migrations: future ALTER TABLE statements would go in
`init_db()` as `CREATE TABLE IF NOT EXISTS` + idempotent `ALTER`s.

## Things I deliberately did NOT add

- **Multi-user / accounts.** This is a personal tool. If you ever need that,
  it should be a different project with proper auth.
- **Photos of vials.** Adds storage + file management complexity for low
  marginal value. The COA verify code is the real proof anyway.
- **Dose-tracking history.** Different concern — that's a journal, not an
  inventory. Could be a sibling app sharing the same DB.
- **Cloud sync.** Personal medical-style data + cloud + no auth is a bad
  combination. Use a sync solution you control (Syncthing, etc.) if you
  want it on multiple machines.
