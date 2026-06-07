# Secret Squirrel 🐿️

A voice **stress / cognitive-load** analyzer with a baseline-comparison protocol.

> ## ⚠️ This is NOT a lie detector.
>
> Peer-reviewed research is clear: **no acoustic feature reliably distinguishes a
> lie from the truth.** Commercial voice stress analyzers (CVSA, LVA / Nemesysco)
> perform at chance level (~50%) in independent evaluations. The
> [Eriksson & Lacerda (2007)](https://www.researchgate.net/publication/236662777_Voice_stress_analyses_Science_and_pseudoscience)
> review of these systems called them "charlatanry." The National Research
> Council (2003) concluded "little or no scientific basis" for VSA technology.
>
> **What this tool actually does:** measures acoustic markers of stress and
> cognitive load (F0 variance, jitter, shimmer, harmonics-to-noise ratio,
> speaking rate, pause patterns) and scores each utterance against the same
> subject's calibrated baseline. Elevated readings indicate the speaker is more
> aroused / strained than during baseline. Stress has many possible causes —
> nervousness, fatigue, recall difficulty, illness, anger, embarrassment — and
> deception is only one of them.
>
> **Do not use this to accuse anyone of lying.** Use it as one of multiple
> signals during a structured interview, the way trained interrogators use it.

## What it does measure (validated science)

Voice-based stress detection has a real evidence base (see the
[PMC12289014 systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12289014/)
of acoustic stress correlates and the
[2025 ScienceDirect review of 12 ML/DL stress-detection studies, 2021-2025](https://www.sciencedirect.com/science/article/abs/pii/S0960077926005138)).
The features extracted here are the gold-standard ones used in that research:

| Feature | What it tracks |
|---|---|
| F0 mean / std | Pitch and pitch variability (sympathetic arousal) |
| Jitter (local) | Cycle-to-cycle pitch period perturbation — laryngeal tension |
| Shimmer (local) | Cycle-to-cycle amplitude perturbation — laryngeal tension |
| HNR | Harmonics-to-noise ratio (lower = strained / breathy) |
| Intensity mean / std | Loudness and loudness variability |
| Speaking rate | Voiced-segment onsets per second |
| Pause ratio | Fraction of utterance without voicing |

Each feature is z-scored against the subject's own baseline distribution and
combined into a composite 0–100 score with a soft saturation curve.

## Install

```bash
cd secret_squirrel
pip install -r requirements.txt
```

Requires a working microphone. `praat-parselmouth` ships its own Praat binary —
no separate install needed. `sounddevice` may require `portaudio`
(`brew install portaudio` on macOS, `apt-get install libportaudio2` on Debian).

## Run

```bash
python -m secret_squirrel.dashboard
# → open http://127.0.0.1:5057
```

Or specify host/port:

```bash
python -m secret_squirrel.dashboard --host 127.0.0.1 --port 5057
```

> Note: binding `--host 0.0.0.0` exposes the dashboard on your LAN with **no
> authentication**. Don't do this unless you mean to.

## Usage protocol

1. **Calibrate (30s).** Subject reads or speaks something emotionally neutral —
   the alphabet, what they had for breakfast, a paragraph from a book. The
   engine collects multiple windowed samples and computes a baseline
   distribution per feature.

2. **Ask questions one at a time.** Label each one. Press "Start question",
   subject answers, the engine auto-stops after ~1.5s of silence and scores
   the answer against the baseline.

3. **Read the per-feature breakdown**, not just the composite. If one specific
   feature is driving the score, that's more interpretable than a single
   number. Recalibrate any time the recording environment changes (different
   mic, different room).

## Recording from a phone (iPhone / Android)

The dashboard's **"Record from this device's mic"** card uses the browser's
native `MediaRecorder` API. It works in Safari on iOS, Chrome on Android,
and any desktop browser — but **iPhone Safari requires HTTPS** for
microphone access. Plain `http://` only works when the URL is `localhost`
or `127.0.0.1`.

Three easy ways to get HTTPS so the iPhone mic capture works:

### Option A — Tailscale Funnel (free, recommended)

```bash
# install Tailscale, log in, then on the dashboard host:
tailscale funnel 5057
# → https://<your-machine>.<your-tailnet>.ts.net is now live
```

Open that URL on your iPhone. HTTPS, signed certificate, no public DNS
needed. Devices on the funnel are limited to ones you log in to.

### Option B — ngrok (free tier works)

```bash
ngrok http 5057
# → https://abc123.ngrok-free.app
```

Faster to set up than Tailscale but anyone with the link can reach the
dashboard. Use a basic-auth flag if you're sharing across the internet:

```bash
ngrok http --basic-auth='you:strong-password' 5057
```

### Option C — Self-signed cert + run Flask in HTTPS mode

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
            -days 30 -nodes -subj '/CN=localhost'
python -m secret_squirrel.dashboard --host 0.0.0.0 --port 5057 \
       --ssl-cert cert.pem --ssl-key key.pem
```

Then on the iPhone, browse to `https://<host-LAN-ip>:5057`, accept the
self-signed cert warning, and the mic card will work.

If you only need uploads (Voice Memo files etc.) and no live phone mic,
plain HTTP on LAN is fine — just bind `--host 0.0.0.0`.

## Architecture

```
secret_squirrel/
├── features.py      # Parselmouth feature extraction
├── baseline.py      # baseline accumulator + z-score scorer
├── voice_engine.py  # state machine, mic stream, VAD utterance segmentation
├── dashboard.py     # Flask SSE dashboard
├── requirements.txt
└── README.md
```

Phase 1 = voice (this).
Phase 2 = facial micro-expression channel (live webcam / video file).
Phase 3 = text message pattern channel.

The composite score will eventually be a weighted sum across the three
channels, but each channel is independently calibrated and independently
interpretable.

## Ethics

Recording someone's voice without their knowledge may be illegal in your
jurisdiction (in the US, "two-party consent" states like CA, FL, MA, WA require
all parties to consent). Get consent.

Even with consent, do not present any composite score from this tool as proof
of deception. It is not.
