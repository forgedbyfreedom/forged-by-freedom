#!/usr/bin/env python3
"""
ECHO dashboard - live acoustic drone detection in your browser.

Run:
  Demo (loops a WAV, no mic needed):
      python3 echo_dashboard.py --wav drone_loud_30s.wav
  Live microphone:
      python3 echo_dashboard.py
  Live 4-mic array with bearing:
      python3 echo_dashboard.py --channels 4 --geometry respeaker

Then open the URL it prints (default http://127.0.0.1:8080).
"""

import argparse
import json
import math
import queue
import threading
import time
import wave

import numpy as np
from flask import Flask, Response, render_template_string, request, jsonify

from echo_engine import EchoEngine, FS, BLOCK
from echo_alerts import AlertManager

_alerts = AlertManager(block_sec=BLOCK / FS)

app = Flask(__name__)
_subscribers = []
_lock = threading.Lock()
_state = {"source": "-", "started": time.time()}
_engine = None   # live detector instance, set by the feed thread
_ML_ON = False   # ML confirmation gate, enabled via --ml
_PLAY = False    # play demo WAV out the speakers, enabled via --play


def _sanitize(result):
    """Replace non-finite floats (NaN/Inf) with None so json.dumps emits valid
    JSON the browser can parse."""
    for k, v in result.items():
        if isinstance(v, float) and not math.isfinite(v):
            result[k] = None
    return result


def publish(result):
    result = _sanitize(result)
    with _lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(result)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def feed_wav(path, loop=True):
    global _engine
    _state["source"] = f"demo: {path}"
    try:
        _feed_wav(path, loop)
    except Exception as ex:
        msg = f"demo feed error: {type(ex).__name__}: {ex}"
        print("  " + msg)
        _state["source"] = msg


def _feed_wav(path, loop=True):
    global _engine
    with wave.open(path, "rb") as w:
        fs, nch = w.getframerate(), w.getnchannels()
        audio = (np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                 .astype(np.float32) / 32768.0).reshape(-1, nch)
    # Resample to the engine's rate so the FFT frequency mapping is correct
    # (the engine assumes FS); a 16k/48k WAV would otherwise read every
    # frequency/RPM wrong.
    if fs != FS:
        n2 = int(audio.shape[0] * FS / fs)
        idx = np.linspace(0, audio.shape[0] - 1, n2)
        audio = np.stack([np.interp(idx, np.arange(audio.shape[0]), audio[:, c])
                          for c in range(nch)], axis=1).astype(np.float32)
        print(f"  [wav] resampled {fs} -> {FS} Hz")
        fs = FS
    eng = EchoEngine(ml=_ML_ON)
    _engine = eng
    block_dt = BLOCK / FS
    mono_full = np.ascontiguousarray(audio[:, 0].astype(np.float32))
    sd = None
    if _PLAY:
        try:
            import sounddevice as _sd
            sd = _sd
            print("  [play] demo audio -> speakers")
        except Exception as ex:
            print(f"  [play] audio output unavailable: {ex}")
            sd = None
    while True:
        if sd is not None:
            try:
                sd.play(mono_full, samplerate=fs)   # whole clip in background; robust on macOS + Windows
            except Exception as ex:
                print(f"  [play] playback error: {ex}")
                sd = None
        for s in range(0, len(audio) - BLOCK, BLOCK):
            blk = audio[s:s + BLOCK]
            eng_blk = blk[:, 0] if nch == 1 else blk
            result = eng.process(eng_blk)
            _alerts.process(result)
            publish(result)
            time.sleep(block_dt)        # pace detection in real time
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
        if not loop:
            break


def feed_mic(channels, geometry):
    global _engine
    _state["source"] = f"live mic ({channels}ch)"
    try:
        import sounddevice as sd
        eng = EchoEngine(geometry=geometry, ml=_ML_ON)
        _engine = eng
        with sd.InputStream(channels=channels, samplerate=FS, blocksize=BLOCK) as stream:
            while True:
                data, _ = stream.read(BLOCK)
                blk = data if channels > 1 else data[:, 0]
                result = eng.process(blk)
                _alerts.process(result)
                publish(result)
    except Exception as ex:
        # A mic that can't do 44.1 kHz (or no input device) would otherwise kill
        # this thread silently, leaving the dashboard running with no data.
        msg = f"mic error: {type(ex).__name__}: {ex}"
        print("  " + msg)
        _state["source"] = msg


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/stream")
def stream():
    def gen():
        q = queue.Queue(maxsize=20)
        with _lock:
            _subscribers.append(q)
        try:
            yield f"data: {json.dumps({'source': _state['source']})}\n\n"
            while True:
                try:
                    result = q.get(timeout=15)
                    yield f"data: {json.dumps(result)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _lock:
                if q in _subscribers:
                    _subscribers.remove(q)
    return Response(gen(), mimetype="text/event-stream")


@app.route("/config", methods=["GET", "POST"])
def config():
    if _engine is None:
        return jsonify({"error": "engine not started yet"}), 503
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        _engine.update_config(
            min_harmonics=data.get("min_harmonics"),
            persist_sec=data.get("persist_sec"),
            harmonic_snr_db=data.get("harmonic_snr_db"),
            min_level_db=data.get("min_level_db"),
            max_drift_hz=data.get("max_drift_hz"),
            min_continuity=data.get("min_continuity"),
        )
    return jsonify(_engine.config())


PAGE = r"""
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ECHO - Acoustic Drone Detection</title>
<style>
  :root{--bg:#0b0f14;--panel:#141b24;--line:#1f2935;--txt:#e9eef3;--mute:#8c98a6;
        --ok:#35c28e;--alert:#ff4d4d;--accent:#ff7a18;--warn:#f5b53d}
  *{box-sizing:border-box;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
  body{margin:0;background:var(--bg);color:var(--txt)}
  header{display:flex;align-items:center;gap:16px;padding:18px 28px;
         background:linear-gradient(90deg,#10161e,#141b24);border-bottom:2px solid var(--accent)}
  .logo{font-size:72px;font-weight:800;letter-spacing:6px;color:var(--accent)}
  .logo small{display:block;font-size:11px;letter-spacing:3px;color:var(--mute);font-weight:600}
  .src{margin-left:auto;color:var(--mute);font-size:13px;text-align:right}
  .wrap{padding:24px 28px;display:grid;grid-template-columns:1.1fr 1fr;gap:20px}
  .status{grid-column:1/3;border-radius:14px;padding:26px 30px;display:flex;
          align-items:center;gap:24px;transition:.3s;border:1px solid var(--line);background:var(--panel)}
  .status.clear{box-shadow:inset 0 0 0 2px rgba(53,194,142,.4)}
  .status.alert{background:#241114;box-shadow:inset 0 0 0 2px var(--alert),0 0 36px rgba(255,77,77,.25);animation:pulse 1.1s infinite}
  @keyframes pulse{0%,100%{box-shadow:inset 0 0 0 2px var(--alert),0 0 24px rgba(255,77,77,.2)}50%{box-shadow:inset 0 0 0 2px var(--alert),0 0 48px rgba(255,77,77,.5)}}
  .dot{width:54px;height:54px;border-radius:50%;flex:0 0 auto;background:var(--ok)}
  .status.alert .dot{background:var(--alert)}
  .status h1{margin:0;font-size:30px;letter-spacing:1px}
  .status p{margin:4px 0 0;color:var(--mute);font-size:14px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 22px}
  .card h2{margin:0 0 14px;font-size:13px;letter-spacing:2px;color:var(--accent);text-transform:uppercase}
  .metrics{display:grid;grid-template-columns:1fr 1fr;gap:14px 22px}
  .metric .v{font-size:26px;font-weight:700}
  .metric .l{font-size:11px;color:var(--mute);letter-spacing:1px;text-transform:uppercase}
  .pill{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700}
  .pill.on{background:rgba(255,122,24,.18);color:var(--accent)}
  .pill.off{background:#1c2530;color:var(--mute)}
  .meter{height:12px;background:#0c1117;border-radius:8px;overflow:hidden;margin-top:6px}
  .meter > i{display:block;height:100%;background:linear-gradient(90deg,var(--ok),var(--warn),var(--alert));width:0%}
  .compass{position:relative;width:160px;height:160px;margin:0 auto;border:2px solid var(--line);border-radius:50%}
  .compass .n{position:absolute;top:4px;left:50%;transform:translateX(-50%);font-size:11px;color:var(--mute)}
  .needle{position:absolute;top:50%;left:50%;width:3px;height:64px;background:var(--accent);
          transform-origin:bottom center;transform:translate(-50%,-100%) rotate(0deg);border-radius:3px;transition:.4s}
  .log{height:230px;overflow:auto;font-family:ui-monospace,Menlo,monospace;font-size:12px;line-height:1.6}
  .log div{padding:2px 0;border-bottom:1px solid #121922;color:var(--mute)}
  .log div.hit{color:var(--txt)} .log div.hit b{color:var(--accent)}
  .foot{grid-column:1/3;color:var(--mute);font-size:11px;text-align:center;margin-top:4px}
  .tune{display:grid;grid-template-columns:1fr 1fr;gap:14px 28px;margin-bottom:14px}
  .tune label{display:block;font-size:12px;color:var(--mute);letter-spacing:1px}
  .tune input[type=range]{width:100%;margin-top:6px;accent-color:var(--accent)}
  .tune label span{color:var(--accent);font-weight:700}
  button#apply{background:var(--accent);color:#10161e;border:0;border-radius:8px;padding:9px 22px;font-weight:700;cursor:pointer}
  #cfgmsg{margin-left:12px;font-size:12px;color:var(--ok)}
  .hint{color:var(--mute);font-size:11px;margin-top:10px}
</style></head><body>
<header>
  <div class="logo">ECHO<small>ACOUSTIC DRONE DETECTION</small></div>
  <div class="src">source: <span id="src">connecting...</span><br><span id="clock"></span></div>
</header>
<div class="wrap">
  <div class="status clear" id="status">
    <div class="dot"></div>
    <div><h1 id="stitle">LISTENING</h1><p id="ssub">No drone signature detected.</p></div>
  </div>

  <div class="card">
    <h2>Signature</h2>
    <div class="metrics">
      <div class="metric"><div class="v" id="bpf">-</div><div class="l">Blade-pass (Hz)</div></div>
      <div class="metric"><div class="v" id="rpm">-</div><div class="l">Implied RPM (2-blade)</div></div>
      <div class="metric"><div class="v" id="harm">-</div><div class="l">Harmonics</div></div>
      <div class="metric"><div class="v" id="snr">-</div><div class="l">SNR (dB)</div></div>
      <div class="metric"><div class="l">Multi-rotor</div><div><span class="pill off" id="multi">-</span></div></div>
      <div class="metric"><div class="l">Flight wobble</div><div><span class="pill off" id="wob">-</span></div></div>
    </div>
    <div style="margin-top:18px"><div class="l" style="color:var(--mute);font-size:11px">INPUT LEVEL</div>
      <div class="meter"><i id="level"></i></div></div>
  </div>

  <div class="card">
    <h2>Bearing</h2>
    <div class="compass"><div class="n">N</div><div class="needle" id="needle"></div></div>
    <p style="text-align:center;color:var(--mute);font-size:12px;margin:12px 0 0">
      <span id="bearing">no array / no lock</span></p>
  </div>

  <div class="card" style="grid-column:1/3">
    <h2>Detection tuning (live)</h2>
    <div class="tune">
      <label>Harmonic sensitivity: <span id="v_snr">-</span> dB
        <input type="range" id="s_snr" min="2" max="12" step="0.5"></label>
      <label>Harmonics required: <span id="v_harm">-</span>
        <input type="range" id="s_harm" min="1" max="5" step="1"></label>
      <label>Persistence: <span id="v_persist">-</span> s
        <input type="range" id="s_persist" min="0.5" max="6" step="0.5"></label>
      <label>Loudness gate: <span id="v_level">-</span> dB
        <input type="range" id="s_level" min="-70" max="-20" step="1"></label>
      <label>Max pitch drift (voice reject): <span id="v_drift">-</span> Hz
        <input type="range" id="s_drift" min="1" max="15" step="0.5"></label>
      <label>Min continuity (reject pauses): <span id="v_cont">-</span>
        <input type="range" id="s_cont" min="0.5" max="1" step="0.05"></label>
    </div>
    <button id="apply">Apply</button><span id="cfgmsg"></span>
    <p class="hint">Lower dB / fewer harmonics / shorter persistence / lower loudness gate = MORE sensitive (and more false alarms). Changes apply instantly, no restart.</p>
  </div>

  <div class="card" style="grid-column:1/3">
    <h2>Detection log</h2>
    <div class="log" id="log"></div>
  </div>
  <div class="foot">ECHO prototype * passive acoustic detection * pair with RF for confirmation before acting</div>
</div>
<script>
const $=id=>document.getElementById(id);
function clock(){$("clock").textContent=new Date().toLocaleTimeString()}
setInterval(clock,1000);clock();
const es=new EventSource("/stream");
es.onmessage=e=>{
  const d=JSON.parse(e.data);
  if(d.source!==undefined){$("src").textContent=d.source;return;}
  // input level meter (-60..0 dB)
  const lv=Math.max(0,Math.min(100,(d.level_db+60)/60*100));
  $("level").style.width=lv+"%";
  if(d.detected){
    $("status").className="status alert";
    $("stitle").textContent="DRONE DETECTED";
    $("ssub").textContent="Acoustic signature confirmed.";
    $("bpf").textContent=d.bpf??"-";
    $("rpm").textContent=d.rpm2??"-";
    $("harm").textContent=d.harmonics;
    $("snr").textContent=d.snr_db;
    setPill("multi",d.multirotor,d.multirotor?("YES "+(d.beat_hz?d.beat_hz+"Hz":"")):"no");
    setPill("wob",d.drone_like,d.drone_like?("DRONE-LIKE "+d.wobble_pct+"%"):"steady");
    if(d.bearing_deg!==null){
      $("needle").style.transform="translate(-50%,-100%) rotate("+d.bearing_deg+"deg)";
      $("bearing").textContent=d.bearing_deg+" deg (conf "+d.bearing_conf+")";
    }
    addLog(d,true);
  }else{
    $("status").className="status clear";
    $("stitle").textContent= d.building? "TRACKING..." : "LISTENING";
    $("ssub").textContent= d.building? "Candidate signature building..." : "No drone signature detected.";
  }
};
function setPill(id,on,txt){const e=$(id);e.className="pill "+(on?"on":"off");e.textContent=txt;}

// --- live tuning sliders ---
const sliders=[["s_snr","v_snr"],["s_harm","v_harm"],["s_persist","v_persist"],["s_level","v_level"],["s_drift","v_drift"],["s_cont","v_cont"]];
function syncLabels(){sliders.forEach(([s,v])=>$(v).textContent=$(s).value);}
sliders.forEach(([s,v])=>$(s).addEventListener("input",syncLabels));
function loadConfig(){
  fetch("/config").then(r=>r.json()).then(c=>{
    if(c.error)return;
    $("s_snr").value=c.harmonic_snr_db; $("s_harm").value=c.min_harmonics;
    $("s_persist").value=c.persist_sec; $("s_level").value=c.min_level_db;
    $("s_drift").value=c.max_drift_hz; $("s_cont").value=c.min_continuity;
    syncLabels();
  }).catch(()=>{});
}
$("apply").addEventListener("click",()=>{
  const body={harmonic_snr_db:+$("s_snr").value, min_harmonics:+$("s_harm").value,
              persist_sec:+$("s_persist").value, min_level_db:+$("s_level").value,
              max_drift_hz:+$("s_drift").value, min_continuity:+$("s_cont").value};
  fetch("/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
    .then(r=>r.json()).then(()=>{ $("cfgmsg").textContent="applied OK";
      setTimeout(()=>$("cfgmsg").textContent="",2000); });
});
loadConfig();
let n=0;
function addLog(d,hit){
  const l=$("log");const div=document.createElement("div");
  if(hit)div.className="hit";
  div.innerHTML=`[t=${d.t}s] <b>BPF ${d.bpf}Hz</b> | ${d.harmonics} harm | ${d.snr_db}dB`
    +(d.multirotor?` | MULTI-ROTOR`:``)
    +(d.bearing_deg!==null?` | ${d.bearing_deg} deg`:``);
  l.prepend(div);
  if(++n>200)l.removeChild(l.lastChild);
}
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="ECHO acoustic drone detection dashboard")
    ap.add_argument("--wav", help="demo mode: loop this WAV instead of the mic")
    ap.add_argument("--channels", type=int, default=1)
    ap.add_argument("--geometry", default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--test-alert", action="store_true",
                    help="send one test alert using current config, then exit")
    ap.add_argument("--ml", action="store_true",
                    help="enable ML confirmation gate (rejects speech/noise the rules pass)")
    ap.add_argument("--play", action="store_true",
                    help="in --wav demo mode, also play the clip out the speakers (cosmetic)")
    args = ap.parse_args()

    global _ML_ON, _PLAY
    _ML_ON = args.ml
    _PLAY = args.play
    print(f"  alerts: {_alerts.status()}")
    print(f"  ML confirmation gate: {'ON' if _ML_ON else 'off'}")
    if args.test_alert:
        _alerts.send_test()
        return

    if args.wav:
        t = threading.Thread(target=feed_wav, args=(args.wav, True), daemon=True)
    else:
        t = threading.Thread(target=feed_mic, args=(args.channels, args.geometry), daemon=True)
    t.start()

    if args.host == "0.0.0.0":
        print("  WARNING: bound to 0.0.0.0 - the dashboard and /config are reachable by")
        print("           anyone on this network (no password). Use only on a trusted LAN.")
    print(f"\n  ECHO dashboard -> http://{args.host}:{args.port}\n  (Ctrl-C to stop)\n")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
