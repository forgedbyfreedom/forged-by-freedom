"""Peptide Tracker — Flask dashboard for on-hand peptide inventory.

Run:    python -m peptide_tracker.app
        → http://127.0.0.1:5058
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import datetime

from flask import Flask, Response, jsonify, request, send_file

from . import db


app = Flask(__name__)


INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<title>Peptide Tracker</title>
<style>
  :root {
    --bg:#0a0d12; --surface:#15191f; --surface-2:#1c2128;
    --border:#2b3140; --border-strong:#3d4452;
    --text:#e8eef5; --text-dim:#8c95a3; --text-faint:#5a6275;
    --primary:#4c8aff; --primary-hover:#3974e6;
    --success:#3ec06d; --warning:#e7b13a; --alert:#ff8c00; --danger:#e3534a;
  }
  * { box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         background:var(--bg); color:var(--text); margin:0; padding:0;
         font-size:14px; line-height:1.5; }
  .container { max-width:1320px; margin:0 auto; padding:0 24px 48px; }

  header { position:sticky; top:0; z-index:50;
           background:rgba(10,13,18,0.92); backdrop-filter:blur(12px);
           border-bottom:1px solid var(--border); padding:14px 0; margin-bottom:18px; }
  header .container { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:22px; font-weight:700; letter-spacing:-0.02em; }
  header h1 .sub { color:var(--text-dim); font-weight:400; font-size:14px; margin-left:6px; }
  header .header-meta { display:flex; gap:14px; align-items:center; flex-wrap:wrap; font-size:12px; color:var(--text-dim); }

  .card { background:var(--surface); border:1px solid var(--border); border-radius:12px;
          padding:18px 20px; margin-bottom:16px; }
  .card h3 { margin:0 0 12px; font-size:15px; font-weight:600;
             text-transform:uppercase; letter-spacing:0.05em; color:var(--text-dim); }
  .card .hint { color:var(--text-dim); font-size:12px; margin:0 0 12px; }

  button { background:var(--primary); color:white; border:0; padding:9px 16px;
           border-radius:8px; font-weight:600; font-size:13px;
           cursor:pointer; transition:all 0.15s; font-family:inherit; }
  button:hover:not(:disabled) { background:var(--primary-hover); transform:translateY(-1px); }
  button.warn  { background:var(--danger); }
  button.warn:hover:not(:disabled)  { background:#c4453d; }
  button.ghost { background:var(--surface-2); color:var(--text); border:1px solid var(--border); }
  button.ghost:hover:not(:disabled) { border-color:var(--border-strong); background:#252b35; }
  button.small { padding:5px 10px; font-size:12px; }
  button:disabled { opacity:0.4; cursor:not-allowed; }

  input[type=text], input[type=number], input[type=date], select, textarea {
    background:var(--surface-2); color:var(--text); border:1px solid var(--border);
    padding:8px 11px; border-radius:8px; font-size:13px; font-family:inherit; width:100%; }
  input:focus, select:focus, textarea:focus { outline:none; border-color:var(--primary); }
  input::placeholder { color:var(--text-faint); }
  textarea { resize:vertical; min-height:60px; }

  .form-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; }
  @media (max-width:900px) { .form-grid { grid-template-columns:repeat(2, 1fr); } }
  @media (max-width:560px) { .form-grid { grid-template-columns:1fr; } }
  .field { display:flex; flex-direction:column; gap:4px; }
  .field label { font-size:11px; color:var(--text-dim); font-weight:600;
                 text-transform:uppercase; letter-spacing:0.05em; }
  .field-full { grid-column:1 / -1; }
  .checkbox-row { display:flex; align-items:center; gap:8px; padding-top:18px; }
  .checkbox-row input { width:auto; }

  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:9px 10px; border-bottom:1px solid var(--border); text-align:left; vertical-align:top; }
  th { color:var(--text-dim); font-weight:500; font-size:11px;
       text-transform:uppercase; letter-spacing:0.05em; }
  tr:last-child td { border-bottom:0; }
  tr.status-warn td { background:rgba(231,177,58,0.05); }
  tr.status-expired td { background:rgba(227,83,74,0.08); }

  .pill { display:inline-block; padding:2px 9px; border-radius:10px;
          font-size:11px; font-weight:700; letter-spacing:0.04em;
          text-transform:uppercase; }
  .pill-ok       { background:rgba(62,192,109,0.12);  color:var(--success); border:1px solid var(--success); }
  .pill-warn     { background:rgba(231,177,58,0.12);  color:var(--warning); border:1px solid var(--warning); }
  .pill-expired  { background:rgba(227,83,74,0.15);   color:#ffb0a8; border:1px solid var(--danger); }
  .pill-powder   { background:var(--surface-2); color:var(--text-dim); border:1px solid var(--border); }
  .pill-fridge   { background:rgba(76,138,255,0.12); color:var(--primary); border:1px solid var(--primary); }
  .pill-freezer  { background:rgba(76,138,255,0.06); color:var(--primary); border:1px solid var(--primary); }
  .pill-room     { background:rgba(231,177,58,0.1); color:var(--warning); border:1px solid var(--warning); }

  .row-buttons { display:flex; gap:6px; }
  .stat-card { background:var(--surface); border:1px solid var(--border);
               border-radius:10px; padding:14px 16px; }
  .stat-card .label { color:var(--text-dim); font-size:11px;
                      text-transform:uppercase; letter-spacing:0.05em; }
  .stat-card .value { font-size:24px; font-weight:700; margin-top:2px; }
  .stats-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px; }
  @media (max-width:700px) { .stats-grid { grid-template-columns:repeat(2,1fr); } }

  .search-row { display:flex; gap:8px; margin-bottom:12px; }
  .search-row input { flex:1; }

  .nowrap { white-space:nowrap; }
  .small-note { font-size:11px; color:var(--text-dim); }
</style></head>
<body>
  <header>
    <div class="container">
      <h1>💉 Peptide Tracker <span class="sub">on-hand inventory</span></h1>
      <div class="header-meta">
        <span id="totalCount">— items</span>
        <button class="ghost small" onclick="window.open('/api/export/json','_blank')">⬇ JSON</button>
        <button class="ghost small" onclick="window.open('/api/export/csv','_blank')">⬇ CSV</button>
      </div>
    </div>
  </header>

  <div class="container">

    <div class="stats-grid">
      <div class="stat-card"><div class="label">Items</div><div class="value" id="statItems">—</div></div>
      <div class="stat-card"><div class="label">Total vials</div><div class="value" id="statVials">—</div></div>
      <div class="stat-card"><div class="label">Need attention</div><div class="value" id="statWarn" style="color:var(--warning);">—</div></div>
      <div class="stat-card"><div class="label">Expired / degraded</div><div class="value" id="statExpired" style="color:var(--danger);">—</div></div>
    </div>

    <div class="card">
      <h3 id="formTitle">Add a peptide</h3>
      <form id="peptideForm">
        <input type="hidden" id="editId" value="">
        <div class="form-grid">
          <div class="field"><label>Name *</label><input type="text" id="name" required placeholder="e.g. HGH 36iu, BPC-157, NAD+"></div>
          <div class="field"><label>Amount / vial</label><input type="number" step="any" id="amount_per_vial" placeholder="36"></div>
          <div class="field"><label>Units</label>
            <select id="units"><option value="mg">mg</option><option value="IU">IU</option><option value="mcg">mcg</option></select>
          </div>
          <div class="field"><label>Vial count</label><input type="number" id="vial_count" value="1"></div>

          <div class="field checkbox-row">
            <input type="checkbox" id="reconstituted">
            <label for="reconstituted" style="text-transform:none;font-size:13px;color:var(--text);font-weight:400;">Reconstituted</label>
          </div>
          <div class="field"><label>Reconst. date</label><input type="date" id="reconstitution_date"></div>
          <div class="field"><label>Bac water (mL)</label><input type="number" step="any" id="bac_water_ml" placeholder="2"></div>
          <div class="field"><label>Expiration</label><input type="date" id="expiration_date"></div>

          <div class="field"><label>Vendor</label><input type="text" id="vendor" placeholder="Toomey / Shengyufan"></div>
          <div class="field"><label>Batch / lot</label><input type="text" id="batch"></div>
          <div class="field"><label>COA verify code</label><input type="text" id="coa_code" placeholder="Janoshik code"></div>
          <div class="field"><label>Cost ($)</label><input type="number" step="any" id="cost" placeholder="0.00"></div>

          <div class="field"><label>Storage</label>
            <select id="storage"><option value="freezer">Freezer</option><option value="fridge">Fridge</option><option value="room">Room temp</option></select>
          </div>
          <div class="field field-full"><label>Notes</label><textarea id="notes" placeholder="dosing, last test, anything"></textarea></div>
        </div>
        <div class="row-buttons" style="margin-top:14px;">
          <button type="submit" id="btnSave">Add to inventory</button>
          <button type="button" class="ghost" id="btnReset">Reset form</button>
        </div>
      </form>
    </div>

    <div class="card">
      <h3>Inventory</h3>
      <div class="search-row">
        <input type="text" id="searchBox" placeholder="Search name, vendor, batch, notes…">
      </div>
      <div style="overflow-x:auto;">
        <table id="invTable">
          <thead><tr>
            <th>Name</th><th>State</th><th>Vials</th><th>Per vial</th>
            <th>Storage</th><th>Vendor</th><th>Notes</th><th></th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <div id="emptyState" class="hint" style="display:none; text-align:center; padding:24px;">
        No items yet. Add your first peptide above.
      </div>
    </div>

  </div>

<script>
const $ = (id) => document.getElementById(id);
let CURRENT = [];

function fmt(n, d = 2) { return (n == null || n === '') ? '—' : (typeof n === 'number' ? n.toFixed(d) : n); }

async function fetchAll(search = '') {
  const r = await fetch('/api/items' + (search ? '?q=' + encodeURIComponent(search) : ''));
  const j = await r.json();
  CURRENT = j.items || [];
  render();
}

function render() {
  // Stats
  $('statItems').textContent = CURRENT.length;
  const totalVials = CURRENT.reduce((s, x) => s + (x.vial_count || 0), 0);
  $('statVials').textContent = totalVials;
  const warn = CURRENT.filter(x => x.status === 'warn').length;
  const expired = CURRENT.filter(x => x.status === 'expired').length;
  $('statWarn').textContent = warn;
  $('statExpired').textContent = expired;
  $('totalCount').textContent = `${CURRENT.length} item${CURRENT.length === 1 ? '' : 's'}`;

  // Table
  const tbody = document.querySelector('#invTable tbody');
  tbody.innerHTML = '';
  $('emptyState').style.display = CURRENT.length === 0 ? 'block' : 'none';

  for (const it of CURRENT) {
    const tr = document.createElement('tr');
    tr.className = 'status-' + (it.status || 'ok');
    const stateBadges = [];
    stateBadges.push(`<span class="pill pill-${it.status}">${it.status === 'ok' ? 'OK' : it.status.toUpperCase()}</span>`);
    if (it.reconstituted) stateBadges.push(`<span class="pill pill-fridge">RECON</span>`);
    else stateBadges.push(`<span class="pill pill-powder">POWDER</span>`);
    const note = it.status_note ? `<div class="small-note">${it.status_note}</div>` : '';
    const amount = (it.amount_per_vial != null ? it.amount_per_vial + ' ' + (it.units || '') : '—');
    const notes = (it.notes || '').slice(0, 80) + ((it.notes || '').length > 80 ? '…' : '');
    tr.innerHTML = `
      <td><b>${escapeHtml(it.name)}</b>${it.batch ? `<div class="small-note">batch ${escapeHtml(it.batch)}</div>` : ''}</td>
      <td>${stateBadges.join(' ')}${note}</td>
      <td>${it.vial_count}</td>
      <td class="nowrap">${amount}</td>
      <td><span class="pill pill-${it.storage}">${(it.storage||'').toUpperCase()}</span></td>
      <td>${escapeHtml(it.vendor || '—')}</td>
      <td><div class="small-note">${escapeHtml(notes || '')}</div></td>
      <td class="row-buttons">
        <button class="ghost small" onclick="loadEdit(${it.id})">Edit</button>
        <button class="warn small" onclick="del(${it.id})">Delete</button>
      </td>`;
    tbody.appendChild(tr);
  }
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function loadEdit(id) {
  const it = CURRENT.find(x => x.id === id);
  if (!it) return;
  $('editId').value = id;
  $('formTitle').textContent = 'Edit — ' + it.name;
  $('btnSave').textContent = 'Save changes';
  for (const k of ['name','amount_per_vial','units','vial_count','reconstitution_date','bac_water_ml','expiration_date','vendor','batch','coa_code','cost','storage','notes']) {
    if ($(k)) $(k).value = it[k] == null ? '' : it[k];
  }
  $('reconstituted').checked = !!it.reconstituted;
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function resetForm() {
  $('peptideForm').reset();
  $('editId').value = '';
  $('formTitle').textContent = 'Add a peptide';
  $('btnSave').textContent = 'Add to inventory';
}
$('btnReset').onclick = resetForm;

async function del(id) {
  const it = CURRENT.find(x => x.id === id);
  if (!confirm(`Delete "${it ? it.name : 'this item'}"? This cannot be undone.`)) return;
  await fetch('/api/items/' + id, {method: 'DELETE'});
  await fetchAll($('searchBox').value);
}

$('peptideForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = {};
  for (const k of ['name','amount_per_vial','units','vial_count','reconstitution_date','bac_water_ml','expiration_date','vendor','batch','coa_code','cost','storage','notes']) {
    data[k] = $(k).value;
  }
  data.reconstituted = $('reconstituted').checked;
  const id = $('editId').value;
  const url = id ? '/api/items/' + id : '/api/items';
  const method = id ? 'PUT' : 'POST';
  const r = await fetch(url, {
    method, headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  const j = await r.json();
  if (j.error) { alert('Error: ' + j.error); return; }
  resetForm();
  await fetchAll($('searchBox').value);
});

$('searchBox').addEventListener('input', () => fetchAll($('searchBox').value));

fetchAll();
</script>
</body></html>
"""


# ── Routes ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return INDEX_HTML


@app.route("/api/items", methods=["GET"])
def list_items():
    search = request.args.get("q", "").strip()
    items = db.list_all(search)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    item_id = db.create(data)
    return jsonify({"ok": True, "id": item_id})


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id: int):
    data = request.get_json(silent=True) or {}
    n = db.update(item_id, data)
    if n == 0:
        return jsonify({"error": "no such item"}), 404
    return jsonify({"ok": True})


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id: int):
    n = db.delete(item_id)
    if n == 0:
        return jsonify({"error": "no such item"}), 404
    return jsonify({"ok": True})


@app.route("/api/export/json")
def export_json():
    items = db.list_all()
    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(items),
        "items": items,
    }
    buf = io.BytesIO(json.dumps(payload, indent=2).encode("utf-8"))
    return send_file(buf, mimetype="application/json", as_attachment=True,
                     download_name=f"peptide-inventory-{datetime.now().strftime('%Y%m%d')}.json")


@app.route("/api/export/csv")
def export_csv():
    items = db.list_all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "id", "name", "vial_count", "amount_per_vial", "units",
        "reconstituted", "reconstitution_date", "days_since_recon",
        "bac_water_ml", "expiration_date", "days_to_expiry",
        "vendor", "batch", "coa_code", "cost", "storage", "status",
        "status_note", "notes", "created_at", "updated_at",
    ])
    for i in items:
        w.writerow([
            i.get("id"), i.get("name"), i.get("vial_count"),
            i.get("amount_per_vial"), i.get("units"),
            "yes" if i.get("reconstituted") else "no",
            i.get("reconstitution_date"), i.get("days_since_recon"),
            i.get("bac_water_ml"), i.get("expiration_date"),
            i.get("days_to_expiry"), i.get("vendor"), i.get("batch"),
            i.get("coa_code"), i.get("cost"), i.get("storage"),
            i.get("status"), i.get("status_note"), i.get("notes"),
            i.get("created_at"), i.get("updated_at"),
        ])
    buf = io.BytesIO(out.getvalue().encode("utf-8"))
    return send_file(buf, mimetype="text/csv", as_attachment=True,
                     download_name=f"peptide-inventory-{datetime.now().strftime('%Y%m%d')}.csv")


def main():
    p = argparse.ArgumentParser(description="Peptide Tracker dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5058)
    args = p.parse_args()
    db.init_db()
    if args.host == "0.0.0.0":
        print("[peptide-tracker] WARNING: binding to 0.0.0.0 exposes the "
              "dashboard with no authentication.")
    print(f"[peptide-tracker] http://{args.host}:{args.port}")
    print(f"[peptide-tracker] db at {db.DB_PATH}")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
