"""Secret Squirrel — Flask dashboard for the voice stress engine."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import tempfile
import time
from datetime import datetime

from flask import Flask, Response, jsonify, request, send_file
from werkzeug.utils import secure_filename

from .voice_engine import VoiceEngine
from .analyzer import analyze_file, analyze_url


# 500 MB cap on uploads — accommodates a long-form interview at modest bitrates
# but stops accidental "the whole podcast archive" from blowing the host out.
MAX_UPLOAD_MB = 500
ALLOWED_AUDIO_EXTS = {
    ".wav", ".aiff", ".aifc", ".flac", ".au",          # native
    ".mp3", ".mp4", ".m4a", ".aac", ".ogg", ".opus",   # common audio
    ".webm", ".mpeg", ".mpga", ".wma", ".amr", ".3gp", # legacy / phone
    ".mkv", ".mov", ".avi",                            # video-with-audio
}


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
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
  .level-accurate { color:#3ec06d; }
  .level-baseline { color:#e7b13a; }
  .level-elevated { color:#ff8c00; }
  .level-extreme  { color:#e3534a; }
  .level-none     { color:#7f8898; }
  .level-pill {
      display:inline-block; padding:4px 12px; border-radius:14px;
      font-weight:700; font-size:13px; letter-spacing:0.4px;
      text-transform:uppercase; margin-top:6px;
  }
  .pill-accurate { background:#173d27; color:#3ec06d; border:1px solid #3ec06d; }
  .pill-baseline { background:#3a2e10; color:#e7b13a; border:1px solid #e7b13a; }
  .pill-elevated { background:#4a2810; color:#ff8c00; border:1px solid #ff8c00; }
  .pill-extreme  { background:#4a1818; color:#ffb0a8; border:1px solid #e3534a;
                   box-shadow:0 0 12px rgba(227,83,74,0.5); }
  .quality-badge { display:inline-block; padding:3px 10px; border-radius:10px;
                   font-size:12px; font-weight:600; margin-left:6px; }
  .quality-good { background:#173d27; color:#3ec06d; border:1px solid #3ec06d; }
  .quality-warn { background:#3a2e10; color:#e7b13a; border:1px solid #e7b13a; }
  .quality-bad  { background:#4a1818; color:#ffb0a8; border:1px solid #e3534a; }
  .quality-none { background:#2b3140; color:#7f8898; border:1px solid #2b3140; }
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
    This tool identifies possible <b>signs of stress or deception in voice
    and thought patterns</b>. It is not a lie detector and offers no
    guarantee of accuracy. Stress has many causes — nervousness, fatigue,
    illness, recall difficulty — and is not by itself proof of deception.
    <b>Do not accuse anyone of lying based on what this tool reports.</b>
  </div>

  <div class="row">
    <div class="card">
      <h3>1. Calibrate baseline</h3>
      <p class="sub">Have your subject read or speak something neutral for ~30s
      (the alphabet, what they ate today, a paragraph from a book).</p>
      <button id="btnCalibrate">Start 30s calibration</button>
      <div id="calStatus" class="sub" style="margin-top:8px;"></div>
      <div id="qualityBadge" style="margin-top:8px;"></div>
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
      <input type="text" id="qTopic" placeholder="topic (optional, groups related Qs)" style="width:40%;margin-top:6px;">
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
    <h3>Upload a recorded conversation</h3>
    <p class="sub">Drop in an audio or video file from your computer or phone
    (WAV, MP3, MP4, M4A, AAC, OGG, OPUS, FLAC, MPEG, WMA, AMR, 3GP, WebM,
    MKV, MOV, AVI — anything ffmpeg reads). Max 500 MB. Use
    <b>"as baseline"</b> on a calm clip first, then <b>"as question"</b> on the
    clip you want scored. The current question-type selector applies.</p>
    <input type="file" id="fileInput" accept="audio/*,video/*,.wav,.mp3,.mp4,.m4a,.aac,.ogg,.opus,.webm,.mpeg,.mpga,.flac,.wma,.amr,.3gp,.aiff,.au,.mkv,.mov,.avi" style="background:#0e1116;color:#e8eef5;padding:8px;">
    <input type="text" id="fileLabel" placeholder="label (optional)" style="width:30%;">
    <br>
    <button id="btnFileCal" class="ghost">Use as baseline</button>
    <button id="btnFileQ">Use as question</button>
    <div id="fileStatus" class="sub" style="margin-top:8px;"></div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>🎙️ Record from this device's mic</h3>
    <p class="sub">Capture audio directly from this device's microphone — iPhone, iPad,
    Mac, PC, anything with a browser. Use as <b>baseline</b> first (30s of neutral
    speech, auto-stops), then as <b>question</b> (you press Stop when the subject
    finishes). Question type selector above applies. Recording uses MediaRecorder
    natively; the audio is uploaded and run through the exact same pipeline as
    file uploads.</p>
    <div id="micCheck" class="sub" style="margin-bottom:8px;"></div>
    <input type="text" id="micLabel" placeholder="label (optional)" style="width:50%;">
    <br>
    <button id="btnMicCal" class="ghost">Start 30s calibration</button>
    <button id="btnMicQ">Start question recording</button>
    <button id="btnMicStop" class="warn" disabled>⏹ Stop & analyze</button>
    <div id="micTimer" class="sub" style="margin-top:8px;"></div>
    <div id="micStatus" class="sub"></div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>Or analyze by URL / server path</h3>
    <p class="sub">Paste a YouTube / X / Instagram / TikTok / direct media URL,
    or a path to a file that's already on this server. yt-dlp handles URL
    fetching.</p>
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
    <h3>Comparison by question type — CQT differential</h3>
    <p class="sub">The Comparison Question Technique compares target answers to
    your own control answers, not just to baseline. The <b>differential</b> is
    <code>mean(target) − mean(control)</code>. A target answer with
    significantly higher stress than your controls is what to follow up on.
    Equal stress across types = nothing to conclude.</p>
    <div id="cqtDiff" style="margin:8px 0 12px 0;"></div>
    <table>
      <thead><tr><th>Type</th><th>n</th><th>Mean stress</th><th>Max</th>
        <th>Mean latency</th></tr></thead>
      <tbody id="typeAgg"></tbody>
    </table>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>Topics — cumulative target evidence</h3>
    <p class="sub">When several target answers share a topic, the per-topic mean
    score is a stronger signal than any single answer. Set the optional
    "topic" field when you ask related questions; this table updates live.</p>
    <table>
      <thead><tr><th>Topic</th><th>n questions</th>
        <th>Mean stress</th><th>Max</th><th>Types</th></tr></thead>
      <tbody id="topicAgg"></tbody>
    </table>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>Per-subject calibration <span id="calibratedBadge"></span></h3>
    <p class="sub">After you know which answers were truthful and which were
    lies, click 👍 (truth) or 👎 (lie) in the History table. Once you have
    ≥3 of each, hit <b>Refit</b> below and the feature weights re-tune to
    what discriminates THIS subject. All history scores recompute immediately
    with the new weights.</p>
    <button id="btnRefit" disabled>Refit weights from labels</button>
    <button id="btnRefitRevert" class="ghost" disabled>Revert to default weights</button>
    <div id="refitStatus" class="sub" style="margin-top:8px;"></div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3 style="display:inline-block;">History</h3>
    <span style="float:right;">
      <button class="ghost" onclick="window.open('/api/export/json','_blank')">Download JSON</button>
      <button class="ghost" onclick="window.open('/api/export/csv','_blank')">Download CSV</button>
    </span>
    <audio id="player" controls style="width:100%;margin:6px 0;display:none;"></audio>
    <table id="histTable">
      <thead><tr><th>▶</th><th>#</th><th>Label</th><th>Topic</th><th>Type</th><th>Stress</th><th>Level</th>
        <th>Latency</th><th>Truth?</th><th>When</th></tr></thead>
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
  const topic = document.getElementById('qTopic').value;
  post('/api/question', {label, question_type: type, topic});
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
  const topic = document.getElementById('qTopic').value;
  const r = await post('/api/analyze', {url, mode, label, question_type, topic});
  document.getElementById('urlStatus').textContent =
    r.error ? ('error: ' + r.error)
            : (r.mode === 'calibrate'
                 ? `baseline locked (${r.baseline_samples} samples, ${r.duration_sec?.toFixed?.(1)}s)`
                 : 'analyzed.');
}
document.getElementById('btnUrlCal').onclick = () => submitUrl('calibrate');
document.getElementById('btnUrlQ').onclick = () => submitUrl('question');

async function submitFile(mode) {
  const fi = document.getElementById('fileInput');
  const status = document.getElementById('fileStatus');
  if (!fi.files || fi.files.length === 0) {
    status.textContent = 'choose a file first'; return;
  }
  const file = fi.files[0];
  const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
  status.textContent = `uploading ${file.name} (${sizeMB} MB)…`;
  const form = new FormData();
  form.append('file', file);
  form.append('mode', mode);
  form.append('label', document.getElementById('fileLabel').value || '');
  form.append('question_type', document.getElementById('qType').value);
  form.append('topic', document.getElementById('qTopic').value || '');
  try {
    const r = await fetch('/api/upload', {method: 'POST', body: form});
    const j = await r.json();
    if (j.error) {
      status.textContent = 'error: ' + j.error;
    } else if (j.mode === 'calibrate') {
      status.textContent = `baseline locked (${j.baseline_samples} samples, ${(j.duration_sec||0).toFixed(1)}s).`;
    } else {
      status.textContent = `analyzed ${file.name}.`;
    }
  } catch (e) {
    status.textContent = 'upload failed: ' + e;
  }
}
document.getElementById('btnFileCal').onclick = () => submitFile('calibrate');
document.getElementById('btnFileQ').onclick   = () => submitFile('question');

// ── Browser MediaRecorder: capture mic on this device ─────────────────
let _mediaRecorder = null, _chunks = [], _recordMode = null,
    _countdown = 0, _countdownInterval = null;

function _pickMimeType() {
  const candidates = [
    'audio/webm;codecs=opus','audio/webm',
    'audio/mp4;codecs=mp4a.40.2','audio/mp4',
    'audio/ogg;codecs=opus','audio/ogg',
  ];
  for (const m of candidates) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported &&
        MediaRecorder.isTypeSupported(m)) return m;
  }
  return '';
}
function _mimeToExt(mime) {
  mime = (mime || '').toLowerCase();
  if (mime.indexOf('webm') >= 0) return '.webm';
  if (mime.indexOf('mp4')  >= 0) return '.m4a';
  if (mime.indexOf('ogg')  >= 0) return '.ogg';
  if (mime.indexOf('wav')  >= 0) return '.wav';
  return '.webm';
}

(function checkMic() {
  const el = document.getElementById('micCheck');
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia ||
      !window.MediaRecorder) {
    el.innerHTML = '<span style="color:#e3534a;">This browser does not support in-browser microphone recording. Use the file-upload card instead.</span>';
    document.getElementById('btnMicCal').disabled = true;
    document.getElementById('btnMicQ').disabled = true;
    return;
  }
  const isSecure = location.protocol === 'https:' ||
                   location.hostname === 'localhost' ||
                   location.hostname === '127.0.0.1';
  if (!isSecure) {
    el.innerHTML = '<span style="color:#e7b13a;">⚠ iPhone Safari (and most browsers) require <b>HTTPS</b> for microphone access. ' +
                   'On HTTP/LAN you can still use the file-upload card. ' +
                   'For HTTPS see the README: <code>tailscale funnel</code>, <code>ngrok http</code>, or a self-signed cert.</span>';
  } else {
    el.textContent = 'Microphone ready. First record press will prompt for permission.';
  }
})();

async function _startMic(mode) {
  _recordMode = mode;
  const status = document.getElementById('micStatus');
  const timer = document.getElementById('micTimer');
  try {
    const stream = await navigator.mediaDevices.getUserMedia(
      {audio: {echoCancellation: true, noiseSuppression: false, autoGainControl: false}}
    );
    const mime = _pickMimeType();
    _mediaRecorder = new MediaRecorder(stream, mime ? {mimeType: mime} : {});
    _chunks = [];
    _mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) _chunks.push(e.data);
    };
    _mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      _uploadMicRecording();
    };
    _mediaRecorder.start();
    document.getElementById('btnMicCal').disabled = true;
    document.getElementById('btnMicQ').disabled = true;
    document.getElementById('btnMicStop').disabled = false;
    status.innerHTML = `<span style="color:#e3534a;">● Recording (${mode})…</span>`;
    // Calibration auto-stops at 30s; question has a 60s hard cap
    _countdown = (mode === 'calibrate') ? 30 : 60;
    timer.textContent = `${mode === 'calibrate' ? 'Auto-stop in ' : '(max '}` +
                        `${_countdown}s${mode === 'calibrate' ? '' : ' — press Stop when done)'}`;
    _countdownInterval = setInterval(() => {
      _countdown -= 1;
      timer.textContent = `${mode === 'calibrate' ? 'Auto-stop in ' : '(max '}` +
                          `${_countdown}s${mode === 'calibrate' ? '' : ' — press Stop when done)'}`;
      if (_countdown <= 0) _stopMic();
    }, 1000);
  } catch (e) {
    status.innerHTML = `<span style="color:#e3534a;">Mic permission denied or unavailable: ${e.message || e.name}</span>`;
  }
}

function _stopMic() {
  if (_mediaRecorder && _mediaRecorder.state === 'recording') _mediaRecorder.stop();
  if (_countdownInterval) { clearInterval(_countdownInterval); _countdownInterval = null; }
  document.getElementById('micTimer').textContent = '';
  document.getElementById('btnMicStop').disabled = true;
}

async function _uploadMicRecording() {
  const status = document.getElementById('micStatus');
  if (_chunks.length === 0) {
    status.textContent = 'No audio captured.';
    document.getElementById('btnMicCal').disabled = false;
    document.getElementById('btnMicQ').disabled = false;
    return;
  }
  status.textContent = 'Analyzing…';
  const mime = _mediaRecorder.mimeType || _chunks[0].type || '';
  const blob = new Blob(_chunks, {type: mime});
  const form = new FormData();
  form.append('file', blob, 'mic_recording' + _mimeToExt(mime));
  form.append('mode', _recordMode);
  form.append('label',
    document.getElementById('micLabel').value || ('mic ' + _recordMode));
  form.append('question_type', document.getElementById('qType').value);
  form.append('topic', document.getElementById('qTopic').value || '');
  try {
    const r = await fetch('/api/upload', {method: 'POST', body: form});
    const j = await r.json();
    if (j.error) status.innerHTML = '<span style="color:#e3534a;">error: ' + j.error + '</span>';
    else if (j.mode === 'calibrate') status.textContent = `Baseline locked (${j.baseline_samples} samples).`;
    else status.textContent = 'Question analyzed — see latest score and history.';
  } catch (e) {
    status.innerHTML = '<span style="color:#e3534a;">Upload failed: ' + e + '</span>';
  }
  document.getElementById('btnMicCal').disabled = false;
  document.getElementById('btnMicQ').disabled = false;
}

document.getElementById('btnMicCal').onclick  = () => _startMic('calibrate');
document.getElementById('btnMicQ').onclick    = () => _startMic('question');
document.getElementById('btnMicStop').onclick = _stopMic;

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
  const q = s.baseline_quality || {level:'none', message:'Not calibrated yet.'};
  document.getElementById('calStatus').textContent = q.message;
  const badge = document.getElementById('qualityBadge');
  if (q.level && q.level !== 'none') {
    const LABEL = {good:'GOOD BASELINE', warn:'THIN BASELINE — recalibrate?', bad:'BAD BASELINE — recalibrate'};
    badge.innerHTML =
      `<span class="quality-badge quality-${q.level}">${LABEL[q.level]||q.level}</span>` +
      `<span class="sub" style="margin-left:8px;">${q.n_samples} sample(s), ${q.total_sec.toFixed(0)}s</span>`;
  } else {
    badge.innerHTML = '';
  }
  const t = s.now_recording_for_sec;
  document.getElementById('recTimer').textContent =
    (s.mode ? `${s.mode} for ${t.toFixed(1)}s` : '');

  const last = s.history && s.history.length ? s.history[s.history.length - 1] : null;
  const gauge = document.getElementById('gauge');
  const gaugeLabel = document.getElementById('gaugeLabel');
  const feats = document.getElementById('features');
  const LEVEL_TEXT = {
    accurate: 'Accurate',
    baseline: 'Baseline',
    elevated: 'Elevated Deception',
    extreme:  'Extreme Deception',
  };
  if (last && last.score && last.score.composite != null) {
    const c = last.score.composite;
    const lv = last.score.level || 'none';
    gauge.textContent = c.toFixed(0);
    gauge.className = 'gauge level-' + lv;
    const labelText = (last.label || 'unlabeled');
    const pillText  = LEVEL_TEXT[lv] || lv;
    gaugeLabel.innerHTML =
      `<div style="margin-bottom:4px;">${labelText}</div>` +
      `<span class="level-pill pill-${lv}">${pillText}</span>`;
    let html = '<table><thead><tr><th>Feature</th><th>This</th><th>Baseline</th><th>z</th><th>Contrib</th></tr></thead><tbody>';
    const fmt = (v) => v == null ? '—' : (typeof v === 'number' ? v.toFixed(3) : v);
    const pf = last.score.per_feature || {};
    for (const k of Object.keys(pf)) {
      const r = pf[k];
      html += `<tr><td>${k}</td><td>${fmt(r.value)}</td><td>${fmt(r.baseline_mean)}</td><td>${fmt(r.z)}</td><td>${fmt(r.stress_contrib)}</td></tr>`;
    }
    html += '</tbody></table>';
    feats.innerHTML = qcHtml + html;
  } else if (last && last.error) {
    gauge.textContent = '!';
    gauge.className = 'gauge level-none';
    gaugeLabel.textContent = last.error;
    feats.textContent = '';
  }

  // Quality + countermeasure warnings (rendered above the feature breakdown)
  let qcHtml = '';
  if (last && last.quality && last.quality.warnings && last.quality.warnings.length) {
    qcHtml += `<div class="disclaimer" style="margin-bottom:8px;"><b>Audio quality warning:</b> ${last.quality.warnings.join(' · ')}.<br>` +
              `<span class="sub">Composite score may be unreliable for this answer.</span></div>`;
  }
  if (last && last.countermeasures && last.countermeasures.length) {
    qcHtml += `<div class="disclaimer" style="margin-bottom:8px;background:#3a2e10;border-color:#e7b13a;color:#f4e0a8;">` +
              `<b>Possible countermeasure:</b> ${last.countermeasures.join('; ')}.<br>` +
              `<span class="sub">Subject may have gamed the baseline calibration. Consider recalibrating from a different neutral prompt.</span></div>`;
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
    // band gridlines: 25 (accurate→baseline), 50 (baseline→elevated), 75 (elevated→extreme)
    [0, 25, 50, 75, 100].forEach(v => {
      const y = yScale(v);
      const ln = document.createElementNS('http://www.w3.org/2000/svg','line');
      ln.setAttribute('x1', 20); ln.setAttribute('x2', W - 20);
      ln.setAttribute('y1', y); ln.setAttribute('y2', y);
      const stroke = v === 25 ? '#3ec06d'
                   : v === 50 ? '#e7b13a'
                   : v === 75 ? '#ff8c00'
                   : '#2b3140';
      ln.setAttribute('stroke', stroke);
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
    // Dots — colored by per-window level (accurate / baseline / elevated / extreme)
    // Each dot has a <title> with the words spoken at that moment, surfaced
    // as a native browser tooltip on hover.
    const DOT = {accurate:'#3ec06d', baseline:'#e7b13a',
                 elevated:'#ff8c00', extreme:'#e3534a'};
    pts.forEach(p => {
      const c = document.createElementNS('http://www.w3.org/2000/svg','circle');
      c.setAttribute('cx', xScale(p.t)); c.setAttribute('cy', yScale(p.composite));
      c.setAttribute('r', p.level === 'extreme' ? 5 : (p.level === 'elevated' ? 4 : 3));
      c.setAttribute('fill', DOT[p.level] || '#7f8898');
      c.style.cursor = 'help';
      const title = document.createElementNS('http://www.w3.org/2000/svg','title');
      title.textContent = `t=${p.t}s  score=${p.composite.toFixed(0)}` +
                          (p.words ? `\n"${p.words}"` : '');
      c.appendChild(title);
      tl.appendChild(c);
    });
    // Peak summary: show the words that were spoken at the peak moment
    const peak = pts.reduce((m,p)=>p.composite>m.composite?p:m, pts[0]);
    const peakWords = peak.words ? ` — at "${peak.words}"` : '';
    meta.innerHTML = `${pts.length} windows across ${tMax.toFixed(1)}s — ` +
                     `<b>peak ${peak.composite.toFixed(0)} at t=${peak.t}s</b>` +
                     peakWords +
                     `<br><span style="opacity:0.7;">Hover any dot to see the words spoken at that moment.</span>`;
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

  // CQT differential: mean(target) - mean(control)
  const diffEl = document.getElementById('cqtDiff');
  const tgt = agg.target, ctrl = agg.control;
  if (tgt && ctrl && tgt.n > 0 && ctrl.n > 0) {
    const diff = (tgt.sum/tgt.n) - (ctrl.sum/ctrl.n);
    let pill = 'pill-baseline', verdict = 'Inconclusive';
    if (diff < 5) { pill = 'pill-accurate'; verdict = 'Targets ≈ Controls'; }
    else if (diff < 15) { pill = 'pill-baseline'; verdict = 'Mild differential'; }
    else if (diff < 25) { pill = 'pill-elevated'; verdict = 'Meaningful differential — follow up'; }
    else { pill = 'pill-extreme'; verdict = 'Strong differential — strong follow up'; }
    const sign = diff >= 0 ? '+' : '';
    diffEl.innerHTML =
      `<div style="font-size:13px;color:#7f8898;">target mean − control mean</div>` +
      `<div style="font-size:32px;font-weight:700;margin:2px 0;">${sign}${diff.toFixed(1)}</div>` +
      `<span class="level-pill ${pill}">${verdict}</span> ` +
      `<span class="sub" style="margin-left:8px;">` +
      `(target ${tgt.n}× mean ${(tgt.sum/tgt.n).toFixed(1)}, ` +
      `control ${ctrl.n}× mean ${(ctrl.sum/ctrl.n).toFixed(1)})` +
      `</span>`;
  } else {
    diffEl.innerHTML =
      `<span class="sub">Need ≥1 control and ≥1 target answer to compute the differential. ` +
      `Use the "control" question type for questions you know the truthful answer to.</span>`;
  }

  // Topic aggregation
  const topics = {};
  (s.history || []).forEach(h => {
    const t = (h.topic || '').trim();
    if (!t) return;
    topics[t] = topics[t] || {n: 0, sum: 0, max: 0, types: new Set()};
    if (h.score && h.score.composite != null) {
      topics[t].n += 1;
      topics[t].sum += h.score.composite;
      if (h.score.composite > topics[t].max) topics[t].max = h.score.composite;
    }
    if (h.type) topics[t].types.add(h.type);
  });
  const topicBody = document.getElementById('topicAgg');
  topicBody.innerHTML = '';
  const topicEntries = Object.entries(topics).sort(
    (a, b) => (b[1].n ? b[1].sum/b[1].n : 0) - (a[1].n ? a[1].sum/a[1].n : 0)
  );
  if (topicEntries.length === 0) {
    topicBody.innerHTML = '<tr><td colspan="5" class="sub">No questions have a topic yet. Set the topic field above when asking related questions.</td></tr>';
  } else {
    topicEntries.forEach(([name, a]) => {
      const mean = a.n > 0 ? (a.sum / a.n).toFixed(1) : '—';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${name}</td><td>${a.n}</td><td>${mean}</td><td>${a.max.toFixed(0)}</td><td>${Array.from(a.types).join(', ')}</td>`;
      topicBody.appendChild(tr);
    });
  }

  // Calibration badge + refit buttons
  const nTruth = (s.history || []).filter(h => h.truth_label === 'truth').length;
  const nLie   = (s.history || []).filter(h => h.truth_label === 'lie').length;
  const calibrated = !!s.calibrated_weights;
  document.getElementById('btnRefit').disabled = !(nTruth >= 3 && nLie >= 3);
  document.getElementById('btnRefitRevert').disabled = !calibrated;
  const calBadge = document.getElementById('calibratedBadge');
  if (calibrated) {
    calBadge.innerHTML = `<span class="level-pill pill-accurate" style="margin-left:8px;">CALIBRATED</span>`;
  } else {
    calBadge.innerHTML = '';
  }
  if (!document.getElementById('refitStatus').textContent) {
    document.getElementById('refitStatus').textContent =
      `${nTruth} truth-labeled, ${nLie} lie-labeled. Refit needs ≥3 of each.`;
  }

  const tbody = document.querySelector('#histTable tbody');
  tbody.innerHTML = '';
  (s.history || []).slice().reverse().forEach((h, idx) => {
    const num = s.history_count - idx;
    const c = (h.score && h.score.composite != null) ? h.score.composite.toFixed(0) : '—';
    const lvl = (h.score && h.score.level) || (h.error || '—');
    const tr = document.createElement('tr');
    const lat = h.response_latency_sec != null ? h.response_latency_sec.toFixed(2) + 's' : '—';
    const playCell = h.audio_path
      ? `<button class="ghost" style="padding:2px 8px;" onclick="playQ(${num})">▶</button>`
      : '<span class="sub">—</span>';
    const tl = h.truth_label || null;
    const upStyle  = tl === 'truth' ? 'background:#173d27;color:#3ec06d;border:1px solid #3ec06d;'
                                    : 'background:#2b3140;color:#7f8898;';
    const dnStyle  = tl === 'lie'   ? 'background:#4a1818;color:#ffb0a8;border:1px solid #e3534a;'
                                    : 'background:#2b3140;color:#7f8898;';
    const truthCell = `<button class="ghost" style="padding:2px 6px;${upStyle}" onclick="labelQ(${num},'truth')" title="Mark truthful">👍</button>` +
                      `<button class="ghost" style="padding:2px 6px;margin-left:2px;${dnStyle}" onclick="labelQ(${num},'lie')" title="Mark lie">👎</button>`;
    tr.innerHTML = `<td>${playCell}</td><td>${num}</td><td>${h.label||''}</td><td>${h.topic||''}</td><td>${h.type||'target'}</td><td>${c}</td><td>${lvl}</td><td>${lat}</td><td>${truthCell}</td><td>${new Date(h.timestamp*1000).toLocaleTimeString()}</td>`;
    tbody.appendChild(tr);
  });
};
async function labelQ(num, label) {
  const cur = await (await fetch('/api/snapshot')).json();
  const existing = (cur.history || [])[num - 1];
  const wasSame = existing && existing.truth_label === label;
  await post('/api/label/' + num, {truth_label: wasSame ? null : label});
}
document.getElementById('btnRefit').onclick = async () => {
  const r = await post('/api/refit', {});
  const s = document.getElementById('refitStatus');
  if (r.error) { s.textContent = 'refit failed: ' + r.error; return; }
  const top = (r.top || []).map(([k,v]) => `${k} ${(v*100).toFixed(0)}%`).join(' · ');
  s.textContent = `Weights refit from ${r.n_truth} truth + ${r.n_lie} lie. Top features: ${top}`;
};
document.getElementById('btnRefitRevert').onclick = async () => {
  await post('/api/refit/revert', {});
  document.getElementById('refitStatus').textContent =
    'Reverted to default weights. History rescored.';
};
function playQ(num) {
  const p = document.getElementById('player');
  p.src = `/api/audio/${num}?t=` + Date.now();
  p.style.display = 'block';
  p.play().catch(() => {});
}
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
        topic=str(body.get("topic", "")),
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
    topic = str(body.get("topic", ""))
    looks_like_url = src.startswith(("http://", "https://"))
    fn = analyze_url if looks_like_url else analyze_file
    result = fn(src, engine, mode=mode, label=label,
                question_type=question_type, topic=topic)
    return jsonify(_sanitize(result))


@app.route("/api/upload", methods=["POST"])
def api_upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"error": "no file uploaded"})
    safe_name = secure_filename(f.filename)
    ext = os.path.splitext(safe_name.lower())[1]
    if ext not in ALLOWED_AUDIO_EXTS:
        return jsonify({"error": f"unsupported file type: {ext or '(none)'}"})
    mode = request.form.get("mode", "question")
    if mode not in ("calibrate", "question"):
        return jsonify({"error": "mode must be 'calibrate' or 'question'"})

    # Save the upload to a temp file with the original extension so ffmpeg
    # picks the right demuxer.
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        f.save(tmp.name)
        tmp.close()
        label = request.form.get("label", "") or safe_name
        question_type = request.form.get("question_type", "target")
        topic = request.form.get("topic", "")
        result = analyze_file(tmp.name, engine, mode=mode, label=label,
                              question_type=question_type, topic=topic)
        return jsonify(_sanitize(result))
    except Exception as e:
        return jsonify({"error": f"analysis failed: {e}"})
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _rescore_history():
    """Re-score every history record against the current baseline / weights.
    Used after a weight refit so the dashboard shows updated composites
    immediately."""
    with engine._lock:
        for h in engine.history:
            feats = h.get("features")
            if feats:
                try:
                    h["score"] = engine.baseline.score(feats)
                except Exception as e:
                    print(f"[secret-squirrel] rescore failed: {e}")


@app.route("/api/label/<int:idx>", methods=["POST"])
def api_label(idx: int):
    """Mark a history record's ground-truth label post-hoc.
    Body: {"truth_label": "truth" | "lie" | null}"""
    body = request.get_json(silent=True) or {}
    val = body.get("truth_label")
    if val not in (None, "truth", "lie"):
        return jsonify({"error": "truth_label must be 'truth', 'lie', or null"})
    with engine._lock:
        if idx < 1 or idx > len(engine.history):
            return jsonify({"error": "no such question"})
        engine.history[idx - 1]["truth_label"] = val
    return jsonify({"ok": True})


@app.route("/api/refit", methods=["POST"])
def api_refit():
    """Fit per-subject feature weights from labeled history.

    Method: for each scoring feature, compute the absolute gap between the
    mean z-score on lie answers and the mean z-score on truth answers
    (|mean(z|lie) − mean(z|truth)|). Features that strongly discriminate
    between truth and lie get bigger weights. Normalize across features so
    they sum to 1, then apply via baseline.set_custom_weights() and re-score
    the entire history so the dashboard updates immediately.

    Requires ≥3 truth-labeled AND ≥3 lie-labeled records to refit.
    """
    import numpy as np
    from .baseline import WEIGHTS
    with engine._lock:
        truths = [h for h in engine.history if h.get("truth_label") == "truth"]
        lies   = [h for h in engine.history if h.get("truth_label") == "lie"]
    if len(truths) < 3 or len(lies) < 3:
        return jsonify({"error":
            f"Need ≥3 truth and ≥3 lie labels. "
            f"You have {len(truths)} truth, {len(lies)} lie."})
    gaps = {}
    for feat in WEIGHTS:
        tzs = [h["score"]["per_feature"][feat]["z"]
               for h in truths
               if isinstance(h.get("score"), dict)
               and feat in (h["score"].get("per_feature") or {})
               and isinstance(h["score"]["per_feature"][feat].get("z"),
                              (int, float))]
        lzs = [h["score"]["per_feature"][feat]["z"]
               for h in lies
               if isinstance(h.get("score"), dict)
               and feat in (h["score"].get("per_feature") or {})
               and isinstance(h["score"]["per_feature"][feat].get("z"),
                              (int, float))]
        if len(tzs) >= 2 and len(lzs) >= 2:
            gaps[feat] = float(abs(np.mean(lzs) - np.mean(tzs)))
    if sum(gaps.values()) <= 0:
        return jsonify({"error": "no discriminative features across labels"})
    engine.baseline.set_custom_weights(gaps)
    _rescore_history()
    return jsonify({
        "ok": True,
        "n_truth": len(truths),
        "n_lie": len(lies),
        "weights": engine.baseline.custom_weights,
        "top": sorted(engine.baseline.custom_weights.items(),
                      key=lambda kv: -kv[1])[:5],
    })


@app.route("/api/refit/revert", methods=["POST"])
def api_refit_revert():
    engine.baseline.clear_custom_weights()
    _rescore_history()
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": f"file exceeds {MAX_UPLOAD_MB} MB limit"}), 413


@app.route("/api/audio/<int:idx>")
def api_audio(idx: int):
    """Serve the per-question WAV (1-indexed to match Q001 file names)."""
    with engine._lock:
        if idx < 1 or idx > len(engine.history):
            return jsonify({"error": "no such question"}), 404
        rec = engine.history[idx - 1]
        path = rec.get("audio_path")
    if not path or not os.path.exists(path):
        return jsonify({"error": "audio not available"}), 404
    return send_file(path, mimetype="audio/wav", as_attachment=False,
                     download_name=f"Q{idx:03d}.wav")


@app.route("/api/export/json")
def api_export_json():
    """One-click full session export — baseline stats + all history."""
    snap = engine.snapshot()
    snap = _sanitize(snap)
    # Stamp the export so users can tell which session is which
    snap["exported_at"] = datetime.now().isoformat(timespec="seconds")
    snap["session_id"] = getattr(engine, "session_id", None)
    fname = f"secret-squirrel-{snap.get('session_id') or 'session'}.json"
    buf = io.BytesIO(json.dumps(snap, indent=2).encode("utf-8"))
    return send_file(buf, mimetype="application/json", as_attachment=True,
                     download_name=fname)


@app.route("/api/export/csv")
def api_export_csv():
    """CSV summary, one row per question — for spreadsheet review."""
    with engine._lock:
        history = list(engine.history)
        session_id = getattr(engine, "session_id", "session")

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "Q#", "label", "type", "source", "timestamp",
        "duration_sec", "response_latency_sec",
        "composite", "level",
        "transcript", "word_count", "hedge_rate", "disfluency_rate",
        "first_person_rate", "words_per_sec",
        "top_feature_1", "top_feature_2", "top_feature_3",
        "audio_path",
    ])
    for i, h in enumerate(history, start=1):
        score = h.get("score") or {}
        per_feat = score.get("per_feature") or {}
        # rank features by stress_contrib for the top-3 columns
        ranked = sorted(per_feat.items(),
                        key=lambda kv: kv[1].get("stress_contrib", 0),
                        reverse=True)
        top = []
        for k, v in ranked[:3]:
            z = v.get("z")
            top.append(f"{k}(z={z:.2f})" if isinstance(z, (int, float))
                       else k)
        top += [""] * (3 - len(top))
        content = h.get("content") or {}
        ts = h.get("timestamp")
        ts_s = (datetime.fromtimestamp(ts).isoformat(timespec="seconds")
                if isinstance(ts, (int, float)) else "")
        w.writerow([
            i,
            h.get("label", ""),
            h.get("type", ""),
            h.get("source", ""),
            ts_s,
            f"{h.get('duration_sec', 0):.2f}",
            (f"{h['response_latency_sec']:.2f}"
             if isinstance(h.get("response_latency_sec"), (int, float))
             else ""),
            (f"{score.get('composite'):.1f}"
             if isinstance(score.get("composite"), (int, float)) else ""),
            score.get("level", ""),
            content.get("text", ""),
            content.get("word_count", ""),
            (f"{content.get('hedge_rate'):.3f}"
             if isinstance(content.get("hedge_rate"), (int, float)) else ""),
            (f"{content.get('disfluency_rate'):.3f}"
             if isinstance(content.get("disfluency_rate"), (int, float)) else ""),
            (f"{content.get('first_person_rate'):.3f}"
             if isinstance(content.get("first_person_rate"), (int, float)) else ""),
            (f"{content.get('words_per_sec'):.2f}"
             if isinstance(content.get("words_per_sec"), (int, float)) else ""),
            top[0], top[1], top[2],
            h.get("audio_path", ""),
        ])
    buf = io.BytesIO(out.getvalue().encode("utf-8"))
    fname = f"secret-squirrel-{session_id}.csv"
    return send_file(buf, mimetype="text/csv", as_attachment=True,
                     download_name=fname)


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
    p.add_argument("--ssl-cert", help="PEM cert for HTTPS (required for iPhone "
                                       "mic capture on a LAN URL)")
    p.add_argument("--ssl-key", help="PEM key for HTTPS")
    p.add_argument("--baseline", help="(CLI mode) WAV/MP3 path or URL for baseline")
    p.add_argument("--question", action="append", default=[],
                   help="(CLI mode) WAV/MP3 path or URL to score; repeatable")
    args = p.parse_args()

    if args.baseline:
        raise SystemExit(_cli_analyze(args.baseline, args.question))

    if args.host == "0.0.0.0":
        print("[secret-squirrel] WARNING: binding to 0.0.0.0 exposes the dashboard "
              "with no authentication.")

    ssl_context = None
    scheme = "http"
    if args.ssl_cert and args.ssl_key:
        if not (os.path.exists(args.ssl_cert) and os.path.exists(args.ssl_key)):
            raise SystemExit(f"--ssl-cert / --ssl-key path not found")
        ssl_context = (args.ssl_cert, args.ssl_key)
        scheme = "https"
    elif bool(args.ssl_cert) != bool(args.ssl_key):
        raise SystemExit("Pass both --ssl-cert and --ssl-key, or neither.")

    print(f"[secret-squirrel] {scheme}://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True,
            ssl_context=ssl_context)


if __name__ == "__main__":
    main()
