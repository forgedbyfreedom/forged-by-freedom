# Secret Squirrel 🐿️

A voice **stress / cognitive-load** analyzer with a baseline-comparison protocol, a content-channel (transcript) layer, in-browser microphone capture, per-subject weight refitting, and audio replay + session export.

> ## Disclaimer
>
> This tool identifies possible **signs of stress or deception in voice and
> thought patterns**. It is **not** a lie detector and offers **no guarantee
> of accuracy**. Stress shows up for many reasons — nervousness, fatigue,
> illness, recall difficulty, anger, embarrassment — and is not by itself
> proof of deception.
>
> **Do not accuse anyone of lying based on what this tool reports.**
> Use the output as one signal among many, not as a verdict.

## Install

```bash
cd secret_squirrel
pip install -r requirements.txt
```

System dependencies:
- **ffmpeg** — required for non-WAV uploads (MP3 / MP4 / M4A / OGG / WebM / etc.) and for URL ingest.
- **portaudio** — only needed if you use the *server-side* live mic recorder. `brew install portaudio` / `apt-get install libportaudio2`.

Optional but recommended:
- **faster-whisper** (in `requirements.txt`) — enables the content channel (transcript → hedge_rate, disfluency_rate, first_person_rate, words_per_sec). Pipeline still works without it; those features just drop out of the score.

## Run

```bash
python -m secret_squirrel.dashboard
# → open http://127.0.0.1:5057
```

Useful flags:

| Flag | Purpose |
|---|---|
| `--host 0.0.0.0` | Bind to LAN. No auth — only use on a Wi-Fi you control. |
| `--port N` | Default 5057. |
| `--ssl-cert cert.pem --ssl-key key.pem` | HTTPS. Required for in-browser mic on iPhone (see [Recording from a phone](#recording-from-a-phone)). |
| `--baseline path/to/wav --question path.wav` | CLI mode for headless scoring (no server). `--question` is repeatable. |

Useful environment variables:

| Var | Default | Meaning |
|---|---|---|
| `SQUIRREL_WHISPER_MODEL` | `tiny` | Whisper model size. Use `base` for actual "um/uh" disfluency capture (the `tiny` model is heavily trained to ignore fillers). Trade-off: ~2× slower transcription, ~145 MB weights download on first use. |

## Four ways to feed it audio

1. **Live mic on the server** ("Ask a question" card). WebRTC-VAD auto-stops the recording after 1.5s of silence. The server-side mic captures from the *host* machine.
2. **Upload a file** — drop in WAV, MP3, MP4, M4A, AAC, OGG, OPUS, FLAC, MPEG, WMA, AMR, 3GP, WebM, MKV, MOV, AVI. 500 MB cap. Routed through ffmpeg → 16 kHz mono WAV.
3. **Record from this device's mic** — uses the browser's native `MediaRecorder`, so it captures from whatever device you're viewing the dashboard on (iPhone, Mac, PC). Requires HTTPS on non-localhost URLs.
4. **URL or server path** — yt-dlp pulls audio from YouTube, X, Instagram, TikTok, podcasts, direct media URLs, ~1000 other sites.

All four routes share the same scoring pipeline and write to the same session directory.

## Usage protocol

1. **Calibrate (30s of neutral speech).** Alphabet, what they had for breakfast, a paragraph from a book. The dashboard surfaces a **baseline quality badge** — green = ≥4 samples / ≥20s, yellow = thin, red = recalibrate.

2. **Set question type and (optionally) topic.**
   - **Type**: `control` (questions you know the truthful answer to), `target` (questions of interest), `buffer` (irrelevant filler), `neutral` (no expectation).
   - **Topic** (optional): groups related questions. The Topics card aggregates target evidence per topic — 5 target answers all averaging ~60 is a much stronger signal than any single 60.

3. **Ask the question. Read the answer.** The dashboard surfaces:
   - **Composite score 0–100** with a band pill (Accurate / Baseline / Elevated Deception / Extreme Deception).
   - **Feature breakdown** — which features drove the score; the *what* of the elevation.
   - **Within-answer timeline** with hover-to-see-words — the *when* and the *what was said*. Look for the words at the peak dot.
   - **Whisper transcript** with content-feature rates (hedge / disfluency / first-person / words-per-sec).
   - **CQT differential** — `mean(target) − mean(control)`, the single number that most matches how real interrogators interpret VSA-style output. Updates live.
   - **Topics table** — per-topic cumulative evidence.

4. **Recalibrate** every 5–10 questions if you suspect the speaker's calm state has drifted (fatigue, rapport). The "Recalibrate (keep history)" button preserves all prior history and just relocks the baseline.

5. **Replay** any answer with the ▶ button in the history table.

6. **Export** the whole session as JSON or CSV from the History card header.

## Per-subject calibration (refit weights from labels)

Once you know which answers were truthful and which were lies (because you knew the answer, or it came out later in conversation):

1. Click 👍 (truth) or 👎 (lie) in the History table next to each answer.
2. When you have **≥3 truth-labeled AND ≥3 lie-labeled** answers, the **"Refit weights from labels"** button activates.
3. Refit computes `|mean(z|lie) − mean(z|truth)|` per scoring feature, normalizes the gaps, and installs them as `baseline.custom_weights`. The entire history rescores immediately with the new weights, and a green **CALIBRATED** pill appears.
4. **Revert to default weights** undoes the override.

On synthetic test data, the refit correctly identifies hedge_rate (43%), shimmer_local (15%), and mfcc_distance (12%) as the top discriminators — the Vrij / Pennebaker deception features rising naturally from the data.

> **Caveat:** the absolute composite levels may drift up or down after refit because the weight distribution concentrates. The discriminative number to read is the **CQT differential**, not the absolute composite. The four bands are still meaningful within a session but should not be cross-compared across sessions or subjects.

## What it measures

### Acoustic channel (always on, Parselmouth / Praat under the hood)

| Feature | Direction | What it tracks |
|---|---|---|
| `f0_mean`, `f0_std` | two-tailed / high | Pitch and pitch variability — sympathetic arousal. |
| `f0_iqr` | high | Robust pitch spread (less sensitive to outliers than std). |
| `f0_slope` | two-tailed | Linear pitch slope across the answer (Hz / sec). |
| `jitter_local` | high | Cycle-to-cycle pitch period perturbation — laryngeal tension. |
| `shimmer_local` | high | Cycle-to-cycle amplitude perturbation — laryngeal tension. |
| `hnr` | low | Harmonics-to-noise ratio (dB). Lower = strained / breathy. |
| `intensity_mean`, `intensity_std` | two-tailed / high | Loudness and loudness variability. |
| `speaking_rate` | two-tailed | Voiced-segment onsets per second. |
| `pause_ratio` | high | Fraction of utterance without voicing. |
| `mfcc_distance` | high | Euclidean distance from the baseline MFCC centroid — spectral-envelope drift. |

### Content channel (Whisper, optional)

| Feature | Direction | What it tracks |
|---|---|---|
| `hedge_rate` | high | Fraction of words that are hedges (`maybe`, `I guess`, `kind of`, `about`, `around`, `apparently`, `might`, …). |
| `disfluency_rate` | high | Fraction that are fillers (`um`, `uh`, `er`, …). Needs `SQUIRREL_WHISPER_MODEL=base` to actually capture them. |
| `first_person_rate` | low | Fraction that are first-person (`I`, `me`, `my`, `we`, …). Pennebaker: truthful narratives use more. |
| `words_per_sec` | two-tailed | Speaking density. |

Each feature is z-scored against the subject's own baseline distribution, weighted (defaults from theory, overridable by refit), capped at 4σ to stop any single feature from blowing up the composite, and combined through a soft-saturation curve `100 · (1 − exp(−z̄))` capped at 100.

## Recording from a phone

The dashboard's **"Record from this device's mic"** card uses the browser's
native `MediaRecorder`. It works in Safari on iOS, Chrome on Android, and any
desktop browser — but **iPhone Safari requires HTTPS** for microphone access.
Plain `http://` only works when the host is `localhost` / `127.0.0.1`.

Three ways to give the iPhone the HTTPS it needs:

### Option A — Tailscale Funnel (recommended)

```bash
tailscale funnel 5057
# → https://<your-machine>.<tailnet>.ts.net
```

Signed cert, no public DNS, access limited to your tailnet.

### Option B — ngrok

```bash
ngrok http --basic-auth='you:strong-password' 5057
# → https://abc123.ngrok-free.app
```

Faster to set up; the basic-auth flag is important if the URL is public.

### Option C — Self-signed cert + the new SSL flags

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
            -days 30 -nodes -subj '/CN=localhost'
python -m secret_squirrel.dashboard --host 0.0.0.0 --port 5057 \
       --ssl-cert cert.pem --ssl-key key.pem
```

Browse to `https://<host-LAN-ip>:5057` on the phone, accept the cert warning, mic works.

If you only need uploads (Voice Memos, screen-recorded calls) and not the live phone mic, plain HTTP on LAN with `--host 0.0.0.0` is fine — uploads work without HTTPS.

## Session storage + export

Every session gets a directory at `~/.secret_squirrel/sessions/<YYYY-MM-DD_HHMMSS>/`. Each question's audio is saved there as `Q001.wav, Q002.wav, …` (16-bit PCM). The dashboard's ▶ button streams them back.

Two export endpoints in the History card header:

- **Download JSON** — full session: baseline stats, calibrated weights, every record with features, score, timeline-with-words, transcript, content features, audio path.
- **Download CSV** — one row per question: Q#, label, type, topic, source, timestamp, duration, response latency, composite, level, transcript, word count, hedge / disfluency / first-person rates, words/sec, top-3 contributing features (with z-scores), audio path.

## Architecture

```
secret_squirrel/
├── features.py       # Parselmouth acoustic feature extraction
├── content.py        # Whisper transcription + content-feature extraction
├── baseline.py       # baseline accumulator, z-score scorer, custom-weights refit
├── voice_engine.py   # state machine, server-side mic, VAD utterance segmentation
├── analyzer.py       # offline file / URL / blob analysis + within-answer timeline
├── dashboard.py      # Flask SSE dashboard, upload, browser-mic, audio replay, export
├── requirements.txt
└── README.md
```

Phase 1 = voice (this).
Phase 2 = facial micro-expression channel (live webcam / video file).
Phase 3 = text message pattern channel.

The composite score will eventually be a weighted sum across the three channels, but each channel will be independently calibrated and independently interpretable.

## Ethics

Recording someone's voice without their knowledge may be illegal in your jurisdiction (in the US, "two-party consent" states like CA, FL, MA, WA require all parties to consent). Get consent.

Even with consent, do not present any composite score or band label from this tool as proof of deception. It is not.
