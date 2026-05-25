# ECHO — Acoustic Drone Detection

Passive acoustic drone detection. ECHO listens through a microphone and flags
the harmonic "buzz" of drone propellers, with a live browser dashboard, voice/
noise rejection, an embedded ML classifier, and optional phone alerts. Runs on
a laptop, Raspberry Pi, or any machine with Python — **no GPU, no cloud, no API
keys.**

## What it does

- **Detects drones** by their blade-pass fundamental (50–700 Hz) and harmonic stack.
- **Rejects false alarms** from speech, fans, dings, and brief sounds via four layers:
  pitch-stability, harmonic-comb, continuity, and an **ML classifier** (trained on
  real drone audio) that confirms drone *timbre* and a **sustained-duration gate**
  (a drone drones on for seconds; a ding doesn't).
- **Live dashboard** at `http://127.0.0.1:8080` — status banner, blade-pass/RPM,
  harmonics, bearing (with a mic array), input meter, detection log, and **live
  tuning sliders** (no restart).
- **Phone alerts** via ntfy (and optional email/SMS).
- **Direction-of-arrival** bearing when fed a multi-mic array.

## Install

```bash
git clone https://github.com/forgedbyfreedom/echo-drone-detector.git
cd echo-drone-detector
pip install -r requirements.txt
```
Requires Python 3.10+. Dependencies: `numpy`, `flask`, `sounddevice` (sounddevice
is only needed for live mic; on Linux/Pi: `sudo apt install libportaudio2` first).

## Run

```bash
# Live microphone, with the ML confirmation gate on (recommended):
python echo_dashboard.py --host 0.0.0.0 --ml

# Demo on a bundled clip (no mic needed):
python echo_dashboard.py --wav real_drone_test.wav --ml

# Demo that ALSO plays the clip through the speakers (for showing people):
python echo_dashboard.py --wav real_drone_test.wav --ml --play
```
Then open **http://127.0.0.1:8080**. (Use `127.0.0.1`, not `0.0.0.0`. To let other
devices on your Wi-Fi view it, keep `--host 0.0.0.0` and browse to the machine's
LAN IP, e.g. `http://192.168.1.x:8080`.)

## Tuning (live, in the dashboard)

Six sliders, applied instantly:
- **Harmonic sensitivity (dB)** / **Harmonics required** — raw detection strength
- **Persistence (s)** — how long a signature must hold
- **Loudness gate (dB)** — ignore near-silence
- **Max pitch drift (Hz)** — reject pitch-gliding voice
- **Min continuity** — reject gappy (speech-like) audio

The **ML threshold** is set with `ECHO_ML_THRESHOLD` (default `0.5`).

## Phone alerts (optional)

```bash
export ECHO_NTFY_TOPIC="your-topic-name"      # subscribe to it in the ntfy app
export ECHO_NTFY_TOKEN="tk_..."               # only for reserved/protected topics
# email/SMS (optional, needs a Gmail App Password):
export ECHO_SMTP_USER="you@gmail.com"
export ECHO_SMTP_PASS="16-char-app-password"
export ECHO_ALERT_TO="you@gmail.com,5551234567@vtext.com"
```
Test alerts: `python echo_dashboard.py --test-alert`

## How detection works

Rules find a harmonic candidate fast; with `--ml`, a small embedded MLP (numpy-only,
weights baked into `echo_ml.py`) confirms it's a drone, requiring ~2.2 s of sustained
positive detection before alerting. This combination detects real drones while
rejecting speech, dings, and brief noises.

## Honest limitations

- **Acoustic is close-in**, not perimeter radar: tens of meters to ~2 km depending
  on drone size and conditions. Wind hurts — use a windscreen outdoors.
- **Testing by playing clips through speakers is unreliable** — speakers can't
  reproduce the low blade-pass frequencies, so playback is missing what defines a
  drone. Validate with the `--wav` demo (clean file) or a **real drone in the air**.
- The ML model is trained on small consumer quads + augmentation. For best results
  on a specific fleet, retrain on recordings of those drones.

## Files

| File | What it is |
|------|-----------|
| `echo_dashboard.py` | Flask dashboard + live config + audio feed |
| `echo_engine.py` | Detection engine (rules, gates, ML-primary logic) |
| `echo_ml.py` | Embedded ML classifier (numpy-only, no model file needed) |
| `echo_alerts.py` | ntfy / email / SMS alerts |
| `drone_detect.py` | Standalone CLI detector (no dashboard) |
| `requirements.txt` | Dependencies |
| `*.wav` | Test/demo clips |

## Note

Passive situational-awareness tool. Operate in compliance with local laws on
recording and monitoring.
