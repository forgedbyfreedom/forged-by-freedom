"""
ECHO Correlation Dashboard — operator-facing live view.

Standalone Flask app showing what the correlation engine is seeing in
real time:

  • Header — live drone-event counters + system health pills
  • Live event feed — last N events from every data source, color-coded
  • Correlation reports — auto-generated when drones detected, with
    ranked candidate cards (inmate + external contact) and the
    evidence trail
  • Network graph — visual link analysis using vis.js. Nodes: inmates,
    external contacts, vehicles, drones. Edges: correlations.
  • Pattern analysis — recurring drone times (heatmap), recurring
    plates near perimeter (top 10), recurring external contacts (top 10)

The dashboard is read-only — it observes the correlation engine via a
shared in-process reference. Designed to be served alongside echo_multi.py
so a single ECHO server process exposes both the orchestrator + the
operator UI.

Run (standalone, useful for demo with synthetic events):
    python echo_correlation_dashboard.py --port 5060

Run (typical — wired into echo_multi.py so the dashboard reflects live
events from real cameras/integrations): see echo_multi.py main() — it
constructs the correlation engine and starts this dashboard against it.
"""
from __future__ import annotations

import argparse
import json
import math
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    """Canonical UTC clock — matches echo_correlation._utcnow so
    comparisons against Event.timestamp (tz-aware after H1) don't
    TypeError. Without this, /api/drone_tracks blows up every request
    the moment any tz-aware event lands in the engine."""
    return datetime.now(timezone.utc)
from pathlib import Path
from typing import Optional

from flask import Flask, Response, jsonify, request

try:
    from .echo_correlation import (CorrelationEngine, CorrelationReport,
                                   Event, DEFAULT_WEIGHTS)
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from echo_correlation import (CorrelationEngine, CorrelationReport,
                                  Event, DEFAULT_WEIGHTS)


# Module-level shared correlation engine reference; the orchestrator
# (echo_multi.py) sets this so the dashboard reflects live events.
_ENGINE: Optional[CorrelationEngine] = None
_REPORTS: list[CorrelationReport] = []   # rolling — newest first
_REPORTS_LOCK = threading.Lock()
_MAX_REPORTS_KEPT = 200
_FACILITY_CENTER: dict = {"lat": 33.8361, "lng": -81.1637}  # SC capitol; overridden by YAML


def set_facility_center(lat: float, lng: float) -> None:
    """Called by echo_multi.py from the YAML config so the map centers correctly."""
    global _FACILITY_CENTER
    _FACILITY_CENTER = {"lat": float(lat), "lng": float(lng)}


def attach_engine(engine: CorrelationEngine) -> None:
    """Wire the orchestrator's correlation engine into the dashboard."""
    global _ENGINE
    _ENGINE = engine
    # Wrap the existing on_report so we capture for the dashboard too
    prior = engine.on_report
    def _multi(report: CorrelationReport):
        with _REPORTS_LOCK:
            _REPORTS.insert(0, report)
            del _REPORTS[_MAX_REPORTS_KEPT:]
        if prior:
            prior(report)
    engine.on_report = _multi


app = Flask(__name__)


INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<title>ECHO — Correlation Dashboard</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {
    --bg:#0a0d12; --surface:#15191f; --surface-2:#1c2128;
    --border:#2b3140; --text:#e8eef5; --text-dim:#8c95a3;
    --primary:#4c8aff; --success:#3ec06d; --warning:#e7b13a;
    --alert:#ff8c00; --danger:#e3534a;
  }
  * { box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:var(--bg); color:var(--text); margin:0; padding:0;
         font-size:13px; line-height:1.5; }
  header { position:sticky; top:0; z-index:50;
           background:rgba(10,13,18,0.96); backdrop-filter:blur(12px);
           border-bottom:1px solid var(--border);
           padding:12px 24px; display:flex; align-items:center;
           justify-content:space-between; gap:16px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:18px; font-weight:700; letter-spacing:-0.02em; }
  header h1 .sub { color:var(--text-dim); font-weight:400; font-size:13px; margin-left:6px; }
  .header-meta { display:flex; gap:14px; font-size:12px; color:var(--text-dim); align-items:center; }
  .stat { display:flex; flex-direction:column; align-items:flex-start; }
  .stat .v { font-size:18px; font-weight:700; color:var(--text); }
  .stat .l { font-size:10px; text-transform:uppercase; letter-spacing:0.06em; }

  .container { padding:16px 24px; max-width:1800px; margin:0 auto; }
  .grid { display:grid; grid-template-columns:380px 1fr 480px; gap:14px; }
  @media (max-width:1400px) { .grid { grid-template-columns:1fr; } }

  .card { background:var(--surface); border:1px solid var(--border);
          border-radius:10px; padding:14px 16px; }
  .card h2 { margin:0 0 10px; font-size:12px; font-weight:600;
             text-transform:uppercase; letter-spacing:0.06em; color:var(--text-dim); }

  .feed { max-height:520px; overflow-y:auto; }
  .ev { padding:6px 8px; border-left:3px solid var(--border); margin-bottom:4px;
        font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11px; }
  .ev .ts { color:var(--text-dim); margin-right:6px; }
  .ev .src { color:var(--primary); margin-right:6px; font-weight:600; }
  .ev-drone_audio    { border-color:var(--alert); }
  .ev-drone_visual   { border-color:var(--danger); }
  .ev-dedrone_detection { border-color:var(--danger); }
  .ev-face           { border-color:var(--primary); }
  .ev-mas_capture    { border-color:#c084fc; }
  .ev-flock_detection{ border-color:#34d399; }
  .ev-dmv_lookup     { border-color:#fbbf24; }
  .ev-cellebrite_call,
  .ev-cellebrite_message,
  .ev-cellebrite_location,
  .ev-cellebrite_app_data { border-color:#a78bfa; }
  .ev-viapath_call   { border-color:#60a5fa; }
  .ev-viapath_visit  { border-color:#60a5fa; }
  .ev-viapath_deposit{ border-color:#60a5fa; }
  .ev-zone_violation { border-color:var(--warning); }

  .report { background:var(--surface-2); border:1px solid var(--border);
            border-radius:10px; padding:12px 14px; margin-bottom:10px; }
  .report .head { display:flex; justify-content:space-between; align-items:center;
                  margin-bottom:8px; flex-wrap:wrap; gap:6px; }
  .report .head .title { font-weight:700; font-size:14px; color:var(--danger); }
  .report .head .ts    { color:var(--text-dim); font-size:11px; }
  .report .signals { display:flex; gap:4px; flex-wrap:wrap; margin-bottom:8px; }
  .pill { display:inline-block; padding:2px 8px; border-radius:9px;
          font-size:10px; font-weight:700; letter-spacing:0.04em;
          text-transform:uppercase; }
  .pill-confirmed { background:rgba(62,192,109,0.12); color:var(--success);
                    border:1px solid var(--success); }
  .pill-serial    { background:rgba(255,140,0,0.15); color:var(--alert);
                    border:1px solid var(--alert); }
  .pill-recovery  { background:rgba(227,83,74,0.18); color:#ffb0a8;
                    border:1px solid var(--danger);
                    box-shadow:0 0 8px rgba(227,83,74,0.5); }
  .candidates { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  @media (max-width:600px) { .candidates { grid-template-columns:1fr; } }
  .cand { background:var(--bg); border:1px solid var(--border);
          border-radius:6px; padding:8px; }
  .cand .nm { font-weight:600; font-size:12px; margin-bottom:2px; }
  .cand .sc { font-size:18px; font-weight:700; }
  .cand .sc.hi { color:var(--danger); }
  .cand .sc.md { color:var(--alert); }
  .cand .sc.lo { color:var(--warning); }
  .cand .sigs { font-size:10px; color:var(--text-dim); margin-top:4px;
                font-family:ui-monospace,monospace; }

  #graph { height:520px; background:var(--bg); border:1px solid var(--border);
           border-radius:8px; }
  #drone-map { height:460px; background:var(--bg); border:1px solid var(--border);
               border-radius:8px; }
  .leaflet-container { background:#0a0d12 !important; }
  .leaflet-tile { filter:brightness(0.85) saturate(0.8); }   /* darken basemap to match theme */
  .drone-track-list { max-height:160px; overflow-y:auto; margin-top:8px; font-size:11px; }
  .drone-track-row { padding:6px 8px; border-left:3px solid var(--danger); margin-bottom:4px;
                     background:var(--surface-2); border-radius:4px; }
  .drone-track-row .id { color:var(--danger); font-weight:700; font-family:ui-monospace,monospace; }
  .drone-track-row .meta { color:var(--text-dim); font-size:10px; margin-top:2px; }
  .drone-track-row .serial { color:var(--alert); font-family:ui-monospace,monospace; }

  .pattern-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }
  @media (max-width:700px) { .pattern-grid { grid-template-columns:1fr; } }
  table { width:100%; border-collapse:collapse; font-size:11px; }
  th,td { padding:5px 6px; text-align:left; border-bottom:1px solid var(--border); }
  th { color:var(--text-dim); font-weight:500; text-transform:uppercase;
       letter-spacing:0.05em; font-size:9px; }

  .heatmap { display:grid; grid-template-columns:repeat(24, 1fr); gap:1px;
             margin-top:8px; }
  .heatcell { height:18px; background:var(--surface-2); border-radius:1px;
              font-size:8px; color:var(--text-dim); text-align:center;
              line-height:18px; }
</style></head>
<body>
  <header>
    <h1>🛰 ECHO <span class="sub">Correlation Dashboard</span></h1>
    <div class="header-meta">
      <div class="stat"><div class="v" id="stat-events">—</div><div class="l">Events ±4h</div></div>
      <div class="stat"><div class="v" id="stat-drones">—</div><div class="l">Drones today</div></div>
      <div class="stat"><div class="v" id="stat-reports">—</div><div class="l">Reports kept</div></div>
      <div class="stat"><div class="v" id="stat-top">—</div><div class="l">Top candidate score</div></div>
    </div>
  </header>

  <div class="container">
    <div class="grid">

      <div class="card">
        <h2>Live Event Feed</h2>
        <div id="feed" class="feed"></div>
      </div>

      <div>
        <div class="card" style="margin-bottom:12px;">
          <h2>Correlation Reports</h2>
          <div id="reports"></div>
        </div>
      </div>

      <div>
        <div class="card" style="margin-bottom:12px;">
          <h2>Network Graph — Subjects & Connections</h2>
          <div id="graph"></div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <h2>Live Drone Map — Dedrone tracks, pilot location, flight history</h2>
      <div id="drone-map"></div>
      <div class="drone-track-list" id="drone-track-list"></div>
      <div style="font-size:10px; color:var(--text-dim); margin-top:6px;">
        🔴 active drone &nbsp;·&nbsp; 🟡 pilot location (when RF-triangulated) &nbsp;·&nbsp;
        🟦 facility &nbsp;·&nbsp; dashed line = flight history (last 10 min)
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <h2>Pattern Analysis</h2>
      <div>
        <div style="font-size:11px; color:var(--text-dim); margin-bottom:4px;">Drone events by hour-of-day (last 30 days)</div>
        <div id="heatmap" class="heatmap"></div>
      </div>
      <div class="pattern-grid">
        <div>
          <h2 style="margin-top:14px;">Top recurring external contacts</h2>
          <table id="top-contacts"><thead><tr><th>Subject</th><th>Events</th><th>Last seen</th></tr></thead><tbody></tbody></table>
        </div>
        <div>
          <h2 style="margin-top:14px;">Top recurring plates near perimeter</h2>
          <table id="top-plates"><thead><tr><th>Plate</th><th>Passes</th><th>Last seen</th></tr></thead><tbody></tbody></table>
        </div>
      </div>
    </div>

  </div>

<script>
const $ = (id) => document.getElementById(id);
const fmt = (n,d=2) => n==null ? '—' : (typeof n === 'number' ? n.toFixed(d) : n);

let network = null, nodesData = null, edgesData = null;

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderFeed(events) {
  const el = $('feed');
  el.innerHTML = events.slice().reverse().map(e => {
    const ts = new Date(e.timestamp).toLocaleTimeString();
    const payload = Object.entries(e.payload).slice(0,3).map(([k,v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' ');
    return `<div class="ev ev-${e.source}"><span class="ts">${ts}</span><span class="src">${e.source}</span> ${escapeHtml(payload)}</div>`;
  }).join('');
}

function renderReports(reports) {
  $('reports').innerHTML = reports.slice(0,5).map(r => {
    const dts = new Date(r.drone_timestamp).toLocaleString();
    const sigBadges = Object.keys(r.drone_signals || {}).map(s => {
      const cls = s.includes('recovery') ? 'pill-recovery' :
                  s.includes('serial')   ? 'pill-serial'   : 'pill-confirmed';
      return `<span class="pill ${cls}">${s.replace(/_/g,' ')}</span>`;
    }).join('');
    const cands = ['inmate_candidates', 'external_candidates'].map(k => {
      const list = (r[k] || []).slice(0,3);
      const label = k === 'inmate_candidates' ? 'Inmate' : 'External';
      return list.map(c => {
        const cls = c.score >= 0.5 ? 'hi' : c.score >= 0.25 ? 'md' : 'lo';
        const sigs = Object.entries(c.signal_scores).slice(0,3).map(([s,v]) => `${s.replace(/_/g,' ')}: ${v.toFixed(2)}`).join('<br>');
        return `<div class="cand"><div class="nm">${label}: ${escapeHtml(c.subject_name || c.subject_id)}</div><div class="sc ${cls}">${c.score.toFixed(3)}</div><div class="sigs">${sigs}</div></div>`;
      }).join('');
    }).join('');
    return `<div class="report"><div class="head"><div><div class="title">DRONE DETECTED — ${escapeHtml(r.drone_camera)}</div><div class="ts">${dts} · conf ${(r.drone_confidence*100).toFixed(0)}%</div></div></div><div class="signals">${sigBadges}</div><div class="candidates">${cands}</div></div>`;
  }).join('');
}

function buildGraph(reports) {
  const nodes = new Map();
  const edges = [];
  reports.slice(0, 8).forEach(r => {
    const droneId = 'drone-' + r.drone_event_id;
    nodes.set(droneId, {id: droneId, label: '🛰 ' + r.drone_camera, color: '#e3534a', shape: 'dot', size: 18});
    (r.inmate_candidates || []).slice(0,3).forEach(c => {
      const id = 'inmate-' + c.subject_id;
      if (!nodes.has(id)) nodes.set(id, {id, label: '👤 ' + (c.subject_name || c.subject_id), color: '#4c8aff', shape: 'dot', size: 14});
      edges.push({from: droneId, to: id, value: c.score, label: c.score.toFixed(2)});
    });
    (r.external_candidates || []).slice(0,3).forEach(c => {
      const id = 'ext-' + c.subject_id;
      if (!nodes.has(id)) nodes.set(id, {id, label: '📞 ' + (c.subject_name || c.subject_id), color: '#ff8c00', shape: 'dot', size: 14});
      edges.push({from: droneId, to: id, value: c.score, label: c.score.toFixed(2)});
    });
  });
  const container = $('graph');
  const data = {nodes: Array.from(nodes.values()), edges};
  const options = {
    nodes: {font: {color: '#e8eef5', size: 11}},
    edges: {font: {color: '#8c95a3', size: 9}, color: '#3d4452',
            arrows: {to: {enabled: true, scaleFactor: 0.5}},
            scaling: {min: 1, max: 5}},
    physics: {stabilization: {iterations: 200}, barnesHut: {gravitationalConstant: -3000}},
    interaction: {hover: true, tooltipDelay: 200},
  };
  if (network) network.destroy();
  network = new vis.Network(container, data, options);
}

function renderHeatmap(buckets) {
  const max = Math.max(...buckets, 1);
  $('heatmap').innerHTML = buckets.map((v, h) => {
    const alpha = v === 0 ? 0.1 : 0.2 + 0.8 * (v / max);
    return `<div class="heatcell" style="background:rgba(227,83,74,${alpha});" title="${h}:00 — ${v} drone events">${h}</div>`;
  }).join('');
}

function renderTable(id, rows) {
  $(id).querySelector('tbody').innerHTML = rows.map(r =>
    `<tr><td>${escapeHtml(r[0])}</td><td>${r[1]}</td><td>${r[2] || '—'}</td></tr>`
  ).join('') || '<tr><td colspan="3" style="color:var(--text-dim);">no data yet</td></tr>';
}

// ── Live drone map (Leaflet) ──────────────────────────────────────
let droneMap = null, droneMapLayers = [];
function initDroneMap(centerLat, centerLng) {
  if (droneMap) return;
  droneMap = L.map('drone-map', {zoomControl: true, attributionControl: false})
    .setView([centerLat, centerLng], 14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(droneMap);
  L.marker([centerLat, centerLng], {
    icon: L.divIcon({className: '', iconSize: [24, 24],
      html: '<div style="background:#4c8aff;border:2px solid #fff;width:22px;height:22px;border-radius:4px;font-size:14px;text-align:center;line-height:18px;">🏢</div>'})
  }).addTo(droneMap).bindPopup('Facility');
}
function renderDroneMap(tracks) {
  if (!droneMap) return;
  droneMapLayers.forEach(l => droneMap.removeLayer(l));
  droneMapLayers = [];
  if (!tracks || tracks.length === 0) return;
  const bounds = [];
  tracks.forEach(t => {
    const hist = t.history || [];
    // Flight history polyline
    if (hist.length > 1) {
      const latlngs = hist.map(p => [p.lat, p.lng]);
      const line = L.polyline(latlngs, {color: '#e3534a', weight: 2, dashArray: '4 4', opacity: 0.7});
      line.addTo(droneMap);
      droneMapLayers.push(line);
      latlngs.forEach(ll => bounds.push(ll));
    }
    // Current drone marker
    if (t.current_lat && t.current_lng) {
      const m = L.marker([t.current_lat, t.current_lng], {
        icon: L.divIcon({className: '', iconSize: [26, 26],
          html: '<div style="background:#e3534a;border:2px solid #fff;width:24px;height:24px;border-radius:50%;font-size:13px;text-align:center;line-height:20px;box-shadow:0 0 10px rgba(227,83,74,0.8);">🛸</div>'})
      }).addTo(droneMap);
      m.bindPopup(
        `<b>${t.classification || 'unknown drone'}</b><br>` +
        `track ${t.track_id}<br>` +
        (t.serial ? `serial: <code>${t.serial}</code><br>` : '') +
        `alt: ${t.current_alt ? t.current_alt.toFixed(0) + 'm' : '—'}<br>` +
        `confidence: ${(t.confidence*100).toFixed(0)}%`);
      droneMapLayers.push(m);
      bounds.push([t.current_lat, t.current_lng]);
    }
    // Pilot location (if Dedrone triangulated it)
    if (t.pilot_lat && t.pilot_lng) {
      const p = L.marker([t.pilot_lat, t.pilot_lng], {
        icon: L.divIcon({className: '', iconSize: [22, 22],
          html: '<div style="background:#e7b13a;border:2px solid #fff;width:20px;height:20px;border-radius:50%;font-size:12px;text-align:center;line-height:17px;">🎮</div>'})
      }).addTo(droneMap);
      p.bindPopup(`<b>Pilot (RF triangulated)</b><br>track ${t.track_id}`);
      droneMapLayers.push(p);
      // Line from pilot to drone
      if (t.current_lat && t.current_lng) {
        const link = L.polyline([[t.pilot_lat, t.pilot_lng], [t.current_lat, t.current_lng]],
          {color: '#e7b13a', weight: 1, dashArray: '2 6', opacity: 0.6});
        link.addTo(droneMap);
        droneMapLayers.push(link);
      }
      bounds.push([t.pilot_lat, t.pilot_lng]);
    }
  });
  if (bounds.length > 0) droneMap.fitBounds(bounds, {padding: [40, 40], maxZoom: 17});
}
function renderDroneTrackList(tracks) {
  $('drone-track-list').innerHTML = (tracks || []).map(t => `
    <div class="drone-track-row">
      <span class="id">${escapeHtml(t.track_id)}</span>
      &nbsp;<span>${escapeHtml(t.classification || 'unknown')}</span>
      ${t.serial ? '&nbsp;⭐ <span class="serial">' + escapeHtml(t.serial) + '</span>' : ''}
      ${t.serial_matches_recovery_case_id ? '&nbsp;<span class="pill pill-recovery">SAME AIRFRAME ' + escapeHtml(t.serial_matches_recovery_case_id) + '</span>' : ''}
      <div class="meta">
        ${t.history.length} positions over ${t.duration_sec.toFixed(0)}s
        ${t.pilot_lat ? ' · 🎮 pilot triangulated' : ' · pilot unknown'}
      </div>
    </div>`).join('') || '<div style="color:var(--text-dim); padding:8px;">No active drone tracks. Dedrone events appear here in real time.</div>';
}

async function refresh() {
  try {
    const s = await (await fetch('/api/snapshot')).json();
    // Init map on first response that has a facility center
    if (s.facility_center && !droneMap) {
      initDroneMap(s.facility_center.lat, s.facility_center.lng);
    }
    const dt = await (await fetch('/api/drone_tracks')).json();
    renderDroneMap(dt.tracks);
    renderDroneTrackList(dt.tracks);
    $('stat-events').textContent  = s.total_events;
    $('stat-drones').textContent  = s.drones_today;
    $('stat-reports').textContent = s.reports_count;
    $('stat-top').textContent     = s.top_candidate_score != null ? s.top_candidate_score.toFixed(3) : '—';
    renderFeed(s.recent_events);
    renderReports(s.reports);
    buildGraph(s.reports);
    renderHeatmap(s.drone_hour_buckets);
    renderTable('top-contacts', s.top_external_contacts);
    renderTable('top-plates',   s.top_plates);
  } catch (e) { console.error(e); }
}
refresh();
setInterval(refresh, 5000);
</script>
</body></html>
"""


# ── Snapshot builder ───────────────────────────────────────────────
def _snapshot() -> dict:
    if _ENGINE is None:
        return {"error": "no correlation engine attached",
                "total_events": 0, "drones_today": 0, "reports_count": 0,
                "top_candidate_score": None, "recent_events": [], "reports": [],
                "drone_hour_buckets": [0] * 24,
                "top_external_contacts": [], "top_plates": []}

    with _ENGINE._lock:
        events = list(_ENGINE._events)
    with _REPORTS_LOCK:
        reports = list(_REPORTS)

    # Drones today (H1 fix: tz-aware — events are tz-aware UTC now)
    today = _utcnow().date()
    drones_today = sum(1 for e in events
                       if e.source in ("drone_audio", "drone_visual", "dedrone_detection")
                       and e.timestamp.date() == today)

    # Recent events (last 60)
    recent = [{
        "source": e.source,
        "timestamp": e.timestamp.isoformat(),
        "payload": {k: v for k, v in e.payload.items()
                    if not isinstance(v, (bytes, bytearray))},
    } for e in events[-60:]]

    # Top candidate score
    top_score = None
    for r in reports:
        for c in (r.inmate_candidates + r.external_candidates):
            if top_score is None or c.score > top_score:
                top_score = c.score

    # 24-hour drone-event heatmap (whole 4-hour window since correlation
    # engine doesn't keep older — for real deployment, separate metrics
    # store would back this)
    buckets = [0] * 24
    for e in events:
        if e.source in ("drone_audio", "drone_visual", "dedrone_detection"):
            buckets[e.timestamp.hour] += 1

    # Top recurring external contacts (from MSISDN appearances)
    msisdn_counter: Counter = Counter()
    msisdn_last: dict = {}
    for e in events:
        m = e.payload.get("msisdn") or e.payload.get("called_number")
        if m:
            msisdn_counter[m] += 1
            msisdn_last[m] = e.timestamp.strftime("%H:%M:%S")
    top_contacts = [(m, c, msisdn_last.get(m, '—')) for m, c in msisdn_counter.most_common(10)]

    # Top recurring plates near perimeter
    plate_counter: Counter = Counter()
    plate_last: dict = {}
    for e in events:
        if e.source == "flock_detection":
            p = e.payload.get("plate")
            if p:
                plate_counter[p] += 1
                plate_last[p] = e.timestamp.strftime("%H:%M:%S")
    top_plates = [(p, c, plate_last.get(p, '—')) for p, c in plate_counter.most_common(10)]

    return {
        "total_events": len(events),
        "drones_today": drones_today,
        "reports_count": len(reports),
        "top_candidate_score": top_score,
        "recent_events": recent,
        "reports": [_report_to_dict(r) for r in reports[:12]],
        "drone_hour_buckets": buckets,
        "top_external_contacts": top_contacts,
        "top_plates": top_plates,
        "facility_center": _FACILITY_CENTER,
    }


def _drone_tracks_snapshot() -> dict:
    """Build live Dedrone-track view: current position, pilot location,
    flight history (last 10 min) per active track."""
    if _ENGINE is None:
        return {"tracks": []}
    with _ENGINE._lock:
        events = list(_ENGINE._by_source.get("dedrone_detection", []))
    # Group by track_id, only keep tracks active in last 5 min
    # H1 fix: tz-aware — events in the engine are tz-aware UTC after H1
    cutoff = _utcnow() - timedelta(minutes=5)
    by_track: dict[str, list] = defaultdict(list)
    for ev in events:
        tid = ev.payload.get("track_id")
        if tid and ev.timestamp >= cutoff - timedelta(minutes=10):  # 10 min of history
            by_track[tid].append(ev)
    tracks = []
    for tid, evs in by_track.items():
        evs.sort(key=lambda e: e.timestamp)
        latest = evs[-1]
        # Only include if "active" (most recent event in last 5 min)
        if latest.timestamp < cutoff:
            continue
        history = [
            {"lat": e.payload.get("position_lat"),
             "lng": e.payload.get("position_lng"),
             "alt": e.payload.get("position_alt_m"),
             "ts":  e.timestamp.isoformat()}
            for e in evs
            if e.payload.get("position_lat") is not None
            and e.payload.get("position_lng") is not None
        ]
        duration = (evs[-1].timestamp - evs[0].timestamp).total_seconds()
        tracks.append({
            "track_id": tid,
            "classification": latest.payload.get("drone_classification"),
            "make": latest.payload.get("drone_make"),
            "model": latest.payload.get("drone_model"),
            "serial": latest.payload.get("drone_serial"),
            "serial_matches_recovery_case_id": latest.payload.get("serial_matches_recovery_case_id"),
            "confidence": latest.payload.get("confidence", 0.0),
            "current_lat": latest.payload.get("position_lat"),
            "current_lng": latest.payload.get("position_lng"),
            "current_alt": latest.payload.get("position_alt_m"),
            "pilot_lat": latest.payload.get("pilot_lat"),
            "pilot_lng": latest.payload.get("pilot_lng"),
            "rf_fingerprint": latest.payload.get("rf_fingerprint"),
            "sensors": latest.payload.get("sensors_contributing", []),
            "history": history,
            "duration_sec": duration,
            "first_seen": evs[0].timestamp.isoformat(),
            "last_seen":  evs[-1].timestamp.isoformat(),
        })
    return {"tracks": tracks}


def _report_to_dict(r: CorrelationReport) -> dict:
    return {
        "drone_event_id": r.drone_event_id,
        "drone_timestamp": r.drone_timestamp.isoformat(),
        "drone_camera": r.drone_camera,
        "drone_confidence": r.drone_confidence,
        "drone_signals": r.drone_signals,
        "drone_signal_evidence": r.drone_signal_evidence,
        "inmate_candidates": [{
            "subject_id": c.subject_id,
            "subject_name": c.subject_name,
            "score": c.score,
            "signal_scores": c.signal_scores,
        } for c in r.inmate_candidates],
        "external_candidates": [{
            "subject_id": c.subject_id,
            "subject_name": c.subject_name,
            "score": c.score,
            "signal_scores": c.signal_scores,
        } for c in r.external_candidates],
    }


# ── Routes ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return INDEX_HTML

@app.route("/api/snapshot")
def api_snapshot():
    return jsonify(_snapshot())

@app.route("/api/drone_tracks")
def api_drone_tracks():
    return jsonify(_drone_tracks_snapshot())


# ── Demo mode — generates synthetic events so the dashboard renders ─
def _seed_demo_events(engine: CorrelationEngine) -> None:
    """Inject synthetic events so the dashboard has something to show."""
    now = _utcnow()
    # Recent inmate observation
    engine.ingest(Event("face", now - timedelta(minutes=3), {
        "inmate_id": "I-12345", "inmate_name": "John Doe",
        "camera_id": "cam-yard-east", "zone_type": "outdoor_yard"}))
    # ViaPath call
    engine.ingest(Event("viapath_call", now - timedelta(minutes=2), {
        "inmate_id": "I-12345", "called_number": "+18435551234",
        "called_party_name": "Outside Contact"}))
    # Flock plate pass
    engine.ingest(Event("flock_detection", now - timedelta(minutes=1), {
        "plate": "ABC1234", "plate_state": "SC",
        "camera_name": "Hwy 17 + 3rd", "hotlist_hit": False}))
    # Dedrone — multiple pings building a flight track + pilot location
    facility = _FACILITY_CENTER
    track_path = [
        # (offset seconds back, dlat, dlng, alt)
        (240, -0.0040, +0.0050, 80),
        (180, -0.0020, +0.0035, 90),
        (120, -0.0005, +0.0020, 100),
        ( 60, +0.0005, +0.0008, 95),
        ( 20, +0.0008, +0.0003, 60),   # closer to facility
        (  0, +0.0010, +0.0001, 30),   # over the yard
    ]
    for back, dlat, dlng, alt in track_path:
        engine.ingest(Event("dedrone_detection", now - timedelta(seconds=back), {
            "track_id": "T-9001",
            "drone_classification": "DJI Mavic 3",
            "drone_make": "DJI", "drone_model": "Mavic 3",
            "drone_serial": "1581F5BNC23A100K0M00",
            "serial_matches_recovery_case_id": "SIU-2026-0078",
            "position_lat": facility["lat"] + dlat,
            "position_lng": facility["lng"] + dlng,
            "position_alt_m": alt,
            "pilot_lat":  facility["lat"] - 0.0050,    # RF-triangulated pilot, 500m away
            "pilot_lng":  facility["lng"] + 0.0070,
            "confidence": 0.94,
            "sensors_contributing": ["rf", "video"],
        }))
    # MAS capture
    engine.ingest(Event("mas_capture", now, {
        "imei": "356123456789012", "msisdn": "+18435551234",
        "rf_cell_id": "housing-block-c"}))
    # The drone event itself (triggers correlation)
    engine.ingest(Event("drone_audio", now, {
        "camera_id": "cam-yard-east", "confidence": 0.78}))


def main():
    p = argparse.ArgumentParser(description="ECHO Correlation Dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5060)
    p.add_argument("--demo", action="store_true",
                   help="Seed with synthetic events for standalone preview")
    args = p.parse_args()
    if args.host == "0.0.0.0":
        print("[corr-dash] WARNING: binding 0.0.0.0 exposes the dashboard with no auth.")
    eng = CorrelationEngine()
    attach_engine(eng)
    if args.demo:
        _seed_demo_events(eng)
        print("[corr-dash] seeded demo events — visit dashboard to see them")
    print(f"[corr-dash] http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
