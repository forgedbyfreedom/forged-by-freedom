"""Secret Squirrel — Flask dashboard for the voice stress engine."""
from __future__ import annotations

import argparse
import json
import math
import time

from flask import Flask, Response, jsonify, request

from .voice_engine import VoiceEngine
from .analyzer import analyze_file, analyze_url


app = Flask(__name__)
engine = VoiceEngine()


INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<title>Secret Squirrel — Voice Stress</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif;
         background:#0e1116; color:#e8eef5; margin:0; padding:24px; }
  h1 { margin:0 0 4px 0; font-size:24px; }
  .sub { color:#7f8898; margin-bottom:18px; font-size:13px; }
  .row { display:flex; gap:16px; flex-wrap:wrap; }
  .card { background:#161a22; border:1px solid #232936; border-radius:10px;
          padding:16px; flex:1 1 320px; }
  button { background:#2a6df4; color:white; border:0; padding:10px 16px;
           border-radius:6px; font-weight:600; cursor:pointer; margin:4px; }
  button.warn { background:#b54023; }
  button.ghost { background:#2b3140; }
  button:disabled { opacity:0.4; cursor:not-allowed; }
  input[type=text] { background:#0e1116; color:#e8eef5; border:1px solid #2b3140;
                     padding:8px; border-radius:6px; width:60%; }
  .gauge { font-size:54px; font-weight:700; text-align:center; }
  .level-low { color:#3ec06d; }
  .level-elevated { color:#e7b13a; }
  .level-high { color:#e3534a; }
  .level-none { color:#7f8898; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:6px 8px; border-bottom:1px solid #232936; text-align:left; }
  th { color:#7f8898; font-weight:500; }
  .bar { height:8px; background:#232936; border-radius:4px; overflow:hidden; }
  .bar > span { display:block; height:100%; background:#2a6df4; }
  .disclaimer { background:#2a1c14; border:1px solid #b54023; color:#f3c8b5;
                padding:10px 14px; border-radius:8px; font-size:13px; margin-bottom:16px; }
  .status-pill { display:inline-block; padding:3px 10px; border-radius:12px;
                 font-size:12px; background:#2b3140; }
  .pill-recording { background:#b54023; }
  .pill-calibrating { background:#7a5b00; }
  .pill-ready { background:#205c34; }
</style></head>
<body>
  <h1>Secret Squirrel</h1>
  <div class="sub">Voice stress &amp; cognitive-load analyzer</div>

  <div class="disclaimer">
    <b>This is not a lie detector.</b> Peer-reviewed research finds no acoustic
    feature reliably distinguishes truth from deception. This tool reports
    <b>stress / cognitive-load markers</b> relative to your subject's own calibrated
    baseline. Stress has many causes — nervousness, fatigue, recall difficulty,
    illness — and is only one possible explanation for elevated readings.
  </div>

  <div class="row">
    <div class="card">
      <h3>1. Calibrate baseline</h3>
      <p class="sub">Have your subject read or speak something neutral for ~30s
      (the alphabet, what they ate today, a paragraph from a book).</p>
      <button id="btnCalibrate">Start 30s calibration</button>
      <div id="calStatus" class="sub" style="margin-top:8px;"></div>
    </div>

    <div class="card">
      <h3>2. Ask a question</h3>
      <p class="sub">Label the question, choose its type, then start recording.
      Stops automatically after 1.5s of silence.</p>
      <input type="text" id="qLabel" placeholder="e.g. Where were you last night?">
      <select id="qType" style="background:#0e1116;color:#e8eef5;border:1px solid #2b3140;padding:8px;border-radius:6px;">
        <option value="target">target</option>
        <option value="control">control</option>
        <option value="buffer">buffer</option>
        <option value="neutral">neutral</option>
      </select>
      <br>
      <button id="btnAsk" disabled>Start question</button>
      <button id="btnStop" class="warn">Stop now</button>
      <button id="btnRecal" class="ghost" disabled>Recalibrate (keep history)</button>
      <button id="btnReset" class="ghost">Reset all</button>
    </div>

    <div class="card">
      <h3>State</h3>
      <div>State: <span id="state" class="status-pill">idle</span></div>
      <div style="margin-top:6px;">Baseline samples: <span id="baseN">0</span></div>
      <div>Questions recorded: <span id="histN">0</span></div>
      <div id="recTimer" class="sub" style="margin-top:6px;"></div>
    </div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>Analyze a video / audio URL or file</h3>
    <p class="sub">Paste a YouTube / X / Instagram / TikTok / direct media URL,
    or a local WAV/MP3 path. yt-dlp will fetch the audio and run it through
    the same pipeline. Use <b>"as baseline"</b> on a neutral clip first, then
    <b>"as question"</b> on the clip you want scored.</p>
    <input type="text" id="urlInput" placeholder="https://…  OR  /path/to/file.wav" style="width:80%;">
    <input type="text" id="urlLabel" placeholder="label (optional)" style="width:30%;">
    <br>
    <button id="btnUrlCal" class="ghost">Use as baseline</button>
    <button id="btnUrlQ">Use as question</button>
    <div id="urlStatus" class="sub" style="margin-top:8px;"></div>
  </div>

  <div class="row" style="margin-top:16px;">
    <div class="card" style="flex:1 1 280px;">
      <h3>Latest score</h3>
      <div id="gauge" class="gauge level-none">—</div>
      <div id="gaugeLabel" class="sub" style="text-align:center;"></div>
    </div>

    <div class="card" style="flex:2 1 540px;">
      <h3>Feature breakdown (last question)</h3>
      <div id="features">Calibrate, then ask a question.</div>
      <div id="content" style="margin-top:12px;"></div>
    </div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>Within-answer stress timeline</h3>
    <p class="sub">Flat = uniform stress across the answer. A spike mid-answer
    is the moment the speaker's voice changed — often where a fabrication is
    constructed or a difficult recall happens. Look for the WHERE.</p>
    <svg id="timeline" width="100%" height="120"
         style="background:#0e1116;border:1px solid #232936;border-radius:8px;"></svg>
    <div id="timelineMeta" class="sub" style="margin-top:4px;"></div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>Comparison by question type</h3>
    <p class="sub">A target answer with significantly higher stress than your
    controls is what to follow up on. Equal stress across types = nothing to
    conclude.</p>
    <table>
      <thead><tr><th>Type</th><th>n</th><th>Mean stress</th><th>Max</th>
        <th>Mean latency</th></tr></thead>
      <tbody id="typeAgg"></tbody>
    </table>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>History</h3>
    <table id="histTable">
      <thead><tr><th>#</th><th>Label</th><th>Type</th><th>Stress</th><th>Level</th>
        <th>Latency</th><th>Duration</th><th>When</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

<script>
async function post(path, body) {
  const r = await fetch(path, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body || {})
  });
  return r.json();
}
document.getElementById('btnCalibrate').onclick = () => post('/api/calibrate', {duration: 30});
document.getElementById('btnAsk').onclick = () => {
  const label = document.getElementById('qLabel').value;
  const type = document.getElementById('qType').value;
  post('/api/question', {label, question_type: type});
};
document.getElementById('btnStop').onclick = () => post('/api/stop');
document.getElementById('btnRecal').onclick = () => {
  if (confirm('Restart baseline calibration (keeps history)?')) post('/api/recalibrate', {duration: 30});
};
document.getElementById('btnReset').onclick = () => {
  if (confirm('Reset baseline and clear all history?')) post('/api/reset');
};
async function submitUrl(mode) {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) { document.getElementById('urlStatus').textContent = 'enter a URL or path'; return; }
  document.getElementById('urlStatus').textContent = 'fetching & analyzing…';
  const label = document.getElementById('urlLabel').value || '';
  const question_type = document.getElementById('qType').value;
  const r = await post('/api/analyze', {url, mode, label, question_type});
  document.getElementById('urlStatus').textContent =
    r.error ? ('error: ' + r.error)
            : (r.mode === 'calibrate'
                 ? `baseline locked (${r.baseline_samples} samples, ${r.duration_sec?.toFixed?.(1)}s)`
                 : 'analyzed.');
}
document.getElementById('btnUrlCal').onclick = () => submitUrl('calibrate');
document.getElementById('btnUrlQ').onclick = () => submitUrl('question');

const evt = new EventSource('/stream');
evt.onmessage = (e) => {
  const s = JSON.parse(e.data);
  const stateEl = document.getElementById('state');
  stateEl.textContent = s.state;
  stateEl.className = 'status-pill pill-' + s.state;
  document.getElementById('baseN').textContent = s.baseline_samples;
  document.getElementById('histN').textContent = s.history_count;
  document.getElementById('btnAsk').disabled = !s.baseline_locked || s.state !== 'ready';
  document.getElementById('btnRecal').disabled = !s.baseline_locked;
  document.getElementById('calStatus').textContent =
    s.baseline_locked ? `Baseline locked (${s.baseline_samples} samples).`
                      : (s.state === 'calibrating' ? 'Calibrating…' : 'Not calibrated yet.');
  const t = s.now_recording_for_sec;
  document.getElementById('recTimer').textContent =
    (s.mode ? `${s.mode} for ${t.toFixed(1)}s` : '');

  const last = s.history && s.history.length ? s.history[s.history.length - 1] : null;
  const gauge = document.getElementById('gauge');
  const gaugeLabel = document.getElementById('gaugeLabel');
  const feats = document.getElementById('features');
  if (last && last.score && last.score.composite != null) {
    const c = last.score.composite;
    gauge.textContent = c.toFixed(0);
    gauge.className = 'gauge level-' + (last.score.level || 'none');
    gaugeLabel.textContent = (last.label || '') + ' — ' + (last.score.level || '');
    let html = '<table><thead><tr><th>Feature</th><th>This</th><th>Baseline</th><th>z</th><th>Contrib</th></tr></thead><tbody>';
    const fmt = (v) => v == null ? '—' : (typeof v === 'number' ? v.toFixed(3) : v);
    const pf = last.score.per_feature || {};
    for (const k of Object.keys(pf)) {
      const r = pf[k];
      html += `<tr><td>${k}</td><td>${fmt(r.value)}</td><td>${fmt(r.baseline_mean)}</td><td>${fmt(r.z)}</td><td>${fmt(r.stress_contrib)}</td></tr>`;
    }
    html += '</tbody></table>';
    feats.innerHTML = html;
  } else if (last && last.error) {
    gauge.textContent = '!';
    gauge.className = 'gauge level-none';
    gaugeLabel.textContent = last.error;
    feats.textContent = '';
  }

  // Content panel (whisper transcript + content features)
  const contentEl = document.getElementById('content');
  if (last && last.content && last.content.text) {
    const ct = last.content;
    contentEl.innerHTML =
      `<div class="sub" style="margin-bottom:6px;"><b>Transcript</b></div>` +
      `<div style="background:#0e1116;padding:8px;border-radius:6px;font-size:13px;">${ct.text}</div>` +
      `<div class="sub" style="margin-top:8px;">` +
      `words: ${ct.word_count} · ${(ct.words_per_sec||0).toFixed(2)}/s · ` +
      `first-person: ${((ct.first_person_rate||0)*100).toFixed(1)}% · ` +
      `hedges: ${((ct.hedge_rate||0)*100).toFixed(1)}% · ` +
      `disfluency: ${((ct.disfluency_rate||0)*100).toFixed(1)}%` +
      `</div>`;
  } else {
    contentEl.innerHTML = '';
  }

  // Within-answer timeline SVG
  const tl = document.getElementById('timeline');
  const meta = document.getElementById('timelineMeta');
  while (tl.firstChild) tl.removeChild(tl.firstChild);
  if (last && last.timeline && last.timeline.length > 0) {
    const W = tl.clientWidth || 600, H = 120;
    const pts = last.timeline;
    const tMax = pts[pts.length-1].t || 1;
    const xScale = (t) => 20 + (t / tMax) * (W - 40);
    const yScale = (c) => H - 15 - (c / 100) * (H - 30);
    // 40 / 70 gridlines
    [0, 40, 70, 100].forEach(v => {
      const y = yScale(v);
      const ln = document.createElementNS('http://www.w3.org/2000/svg','line');
      ln.setAttribute('x1', 20); ln.setAttribute('x2', W - 20);
      ln.setAttribute('y1', y); ln.setAttribute('y2', y);
      ln.setAttribute('stroke', v === 40 ? '#3ec06d' : v === 70 ? '#e7b13a' : '#2b3140');
      ln.setAttribute('stroke-dasharray', '3,3');
      tl.appendChild(ln);
      const tx = document.createElementNS('http://www.w3.org/2000/svg','text');
      tx.setAttribute('x', 4); tx.setAttribute('y', y + 4);
      tx.setAttribute('fill', '#7f8898'); tx.setAttribute('font-size', '10');
      tx.textContent = v;
      tl.appendChild(tx);
    });
    // Path
    let d = '';
    pts.forEach((p, i) => {
      const x = xScale(p.t), y = yScale(p.composite);
      d += (i ? 'L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1) + ' ';
    });
    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', '#2a6df4');
    path.setAttribute('stroke-width', '2');
    tl.appendChild(path);
    // Dots
    pts.forEach(p => {
      const c = document.createElementNS('http://www.w3.org/2000/svg','circle');
      c.setAttribute('cx', xScale(p.t)); c.setAttribute('cy', yScale(p.composite));
      c.setAttribute('r', 3);
      c.setAttribute('fill', p.level === 'high' ? '#e3534a'
                          : p.level === 'elevated' ? '#e7b13a' : '#3ec06d');
      tl.appendChild(c);
    });
    meta.textContent = `${pts.length} windows across ${tMax.toFixed(1)}s — peak ${Math.max(...pts.map(p=>p.composite)).toFixed(0)} at t=${pts.reduce((m,p)=>p.composite>m.composite?p:m, pts[0]).t}s`;
  } else {
    meta.textContent = '';
  }

  // Type aggregation
  const agg = {};
  (s.history || []).forEach(h => {
    const t = h.type || 'target';
    agg[t] = agg[t] || {n:0, sum:0, max:0, latencySum:0, latencyN:0};
    if (h.score && h.score.composite != null) {
      agg[t].n += 1;
      agg[t].sum += h.score.composite;
      if (h.score.composite > agg[t].max) agg[t].max = h.score.composite;
    }
    if (h.response_latency_sec != null) {
      agg[t].latencySum += h.response_latency_sec;
      agg[t].latencyN += 1;
    }
  });
  const aggBody = document.getElementById('typeAgg');
  aggBody.innerHTML = '';
  ['control','buffer','target','neutral'].forEach(t => {
    const a = agg[t]; if (!a || a.n === 0) return;
    const tr = document.createElement('tr');
    const meanLat = a.latencyN > 0 ? (a.latencySum / a.latencyN).toFixed(2) + 's' : '—';
    tr.innerHTML = `<td>${t}</td><td>${a.n}</td><td>${(a.sum/a.n).toFixed(1)}</td><td>${a.max.toFixed(0)}</td><td>${meanLat}</td>`;
    aggBody.appendChild(tr);
  });

  const tbody = document.querySelector('#histTable tbody');
  tbody.innerHTML = '';
  (s.history || []).slice().reverse().forEach((h, idx) => {
    const c = (h.score && h.score.composite != null) ? h.score.composite.toFixed(0) : '—';
    const lvl = (h.score && h.score.level) || (h.error || '—');
    const tr = document.createElement('tr');
    const lat = h.response_latency_sec != null ? h.response_latency_sec.toFixed(2) + 's' : '—';
    tr.innerHTML = `<td>${s.history_count - idx}</td><td>${h.label||''}</td><td>${h.type||'target'}</td><td>${c}</td><td>${lvl}</td><td>${lat}</td><td>${(h.duration_sec||0).toFixed(1)}s</td><td>${new Date(h.timestamp*1000).toLocaleTimeString()}</td>`;
    tbody.appendChild(tr);
  });
};
</script>
</body></html>
"""


def _sanitize(o):
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            return None
        return o
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    return o


@app.route("/")
def index():
    return INDEX_HTML


@app.route("/api/calibrate", methods=["POST"])
def api_calibrate():
    body = request.get_json(silent=True) or {}
    return jsonify(engine.start_calibration(duration_sec=body.get("duration", 30.0)))


@app.route("/api/question", methods=["POST"])
def api_question():
    body = request.get_json(silent=True) or {}
    return jsonify(engine.start_question(
        label=str(body.get("label", "")),
        question_type=str(body.get("question_type", "target")),
    ))


@app.route("/api/stop", methods=["POST"])
def api_stop():
    return jsonify(engine.stop())


@app.route("/api/recalibrate", methods=["POST"])
def api_recalibrate():
    body = request.get_json(silent=True) or {}
    return jsonify(engine.recalibrate(duration_sec=body.get("duration", 30.0)))


@app.route("/api/reset", methods=["POST"])
def api_reset():
    return jsonify(engine.reset())


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    body = request.get_json(silent=True) or {}
    src = (body.get("url") or "").strip()
    if not src:
        return jsonify({"error": "url or path required"})
    mode = body.get("mode", "question")
    if mode not in ("calibrate", "question"):
        return jsonify({"error": "mode must be 'calibrate' or 'question'"})
    label = str(body.get("label", ""))
    question_type = str(body.get("question_type", "target"))
    looks_like_url = src.startswith(("http://", "https://"))
    fn = analyze_url if looks_like_url else analyze_file
    result = fn(src, engine, mode=mode, label=label,
                question_type=question_type)
    return jsonify(_sanitize(result))


@app.route("/api/snapshot")
def api_snapshot():
    return jsonify(_sanitize(engine.snapshot()))


@app.route("/stream")
def stream():
    def gen():
        last = None
        while True:
            try:
                snap = _sanitize(engine.snapshot())
                blob = json.dumps(snap)
                if blob != last:
                    yield f"data: {blob}\n\n"
                    last = blob
                time.sleep(0.3)
            except GeneratorExit:
                break
            except Exception as e:
                print(f"[secret-squirrel] stream error: {e}")
                time.sleep(1.0)
    return Response(gen(), mimetype="text/event-stream")


def _cli_analyze(baseline_src: str, question_srcs: list[str]):
    """Headless mode: calibrate on one file/URL, then score one or more questions."""
    print(f"[secret-squirrel] calibrating on: {baseline_src}")
    fn = analyze_url if baseline_src.startswith(("http://", "https://")) else analyze_file
    r = fn(baseline_src, engine, mode="calibrate", label="baseline")
    if r.get("error"):
        print(f"[secret-squirrel] calibration failed: {r['error']}")
        return 1
    print(f"  baseline locked: {r.get('baseline_samples')} samples, "
          f"{r.get('duration_sec'):.1f}s audio")

    for q in question_srcs:
        print(f"[secret-squirrel] question: {q}")
        fn = analyze_url if q.startswith(("http://", "https://")) else analyze_file
        r = fn(q, engine, mode="question", label=q)
        if r.get("error"):
            print(f"  ERROR: {r['error']}")
            continue
        rec = r.get("record", {})
        score = rec.get("score", {})
        composite = score.get("composite")
        level = score.get("level")
        print(f"  composite: {composite:.1f}/100  level: {level}"
              if composite is not None else "  composite: n/a")
        pf = score.get("per_feature", {})
        for k, v in pf.items():
            print(f"    {k:18s} z={v['z']:+.2f}  contrib={v['stress_contrib']:.2f}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Secret Squirrel voice stress dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5057)
    p.add_argument("--baseline", help="(CLI mode) WAV/MP3 path or URL for baseline")
    p.add_argument("--question", action="append", default=[],
                   help="(CLI mode) WAV/MP3 path or URL to score; repeatable")
    args = p.parse_args()

    if args.baseline:
        raise SystemExit(_cli_analyze(args.baseline, args.question))

    if args.host == "0.0.0.0":
        print("[secret-squirrel] WARNING: binding to 0.0.0.0 exposes the dashboard "
              "with no authentication.")
    print(f"[secret-squirrel] http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
