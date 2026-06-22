# ECHO — Acoustic Drone Detection (+ Correctional Drone & Inmate Monitoring)

ECHO started as a single-mic acoustic drone detector and has grown into a
multi-camera, multi-modal correctional facility security platform that
combines audio detection, computer vision, facial recognition, vendor
data feeds (ViaPath / Tecore MAS), and cross-system link analysis to
identify who's behind a drone incursion.

> **Two ways to use this codebase:**
>
> 1. **As a single-mic drone detector** for home / property use →
>    use `echo_dashboard.py` as documented in the original section below.
> 2. **As a correctional drone + inmate monitoring + link-analysis
>    system** → use `echo_multi.py` driven by `echo_cameras.yaml`.
>    Architecture in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## Quick start (single-mic mode)

```bash
pip install -r requirements.txt
python echo_dashboard.py            # live mic, browser at http://127.0.0.1:5050
python echo_dashboard.py --wav file.wav     # analyze a WAV file
```

See `ACOUSTIC_DETECTION_RESEARCH.md` for the science behind the detection
algorithm (BPF/harmonic stacks, persistence tracking, ML confirmation
layer).

---

## Quick start (correctional multi-camera mode)

```bash
pip install -r requirements.txt
# Edit echo_cameras.yaml with your camera RTSP URLs + zones
python echo_multi.py --config echo_cameras.yaml
```

The orchestrator:
- Spins up one acoustic detector per camera (existing audio engine + new RTSP source)
- Wires placeholder vision + facial-recognition workers per camera
- Loads zone rules from YAML
- Runs cross-system link analysis on every drone event
- Routes named alerts to configured channels

**Most subsystems are runnable today; vendor integrations are
clearly-marked placeholders** waiting on data-sharing contracts.
Architecture document explains every module's status:
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## Module map

```
echo/
├── echo_engine.py        OK  acoustic detection (BPF, harmonics, persistence, ML)
├── echo_ml.py            OK  numpy-only MLP for drone confirmation
├── echo_alerts.py        OK  multi-channel alert dispatch (email, SMS, ntfy + routing)
├── echo_dashboard.py     OK  Flask SSE single-mic dashboard
├── echo_rtsp.py          OK  RTSP audio ingestion via ffmpeg
├── echo_cameras.yaml     OK  multi-camera + zones + alert-routing config
├── echo_zones.py         OK  inmate access rules (hours, classification)
├── echo_correlation.py   OK  rolling event log + link-analysis engine
├── echo_multi.py         OK  orchestrator: ties everything together
├── echo_vision.py        ··  PLACEHOLDER — YOLO interface (drone, phone, violence)
├── echo_face.py          ··  PLACEHOLDER — facial recognition + inmate DB
├── echo_viapath.py       ··  PLACEHOLDER — ViaPath/GTL/IRT data integration
├── echo_tecore.py        ··  PLACEHOLDER — Tecore MAS contraband-phone integration
├── ARCHITECTURE.md       full system design + procurement + legal
├── ACOUSTIC_DETECTION_RESEARCH.md   the science behind the audio detector
└── README.md             this file
```

`OK` = runnable today;  `··` = scaffold + clearly marked `# PLACEHOLDER`
for vendor wiring.

---

## What "link analysis" actually does — worked example

A drone is detected over Yard A at 14:32:15 by `cam-yard-east`'s
microphone. The correlation engine immediately runs against the past
4 hours of events and produces a report. The signals it finds:

| Subject | Signal | Score |
|---|---|---|
| Inmate I-12345 (John Doe) | seen on cam-yard-east 2 min before drone (face) | 0.60 |
| Inmate I-12345 | on ViaPath call 1 min before drone | 0.80 |
| External contact +1-202-555-1234 | called inmate I-12345 1 min before drone | 0.98 |
| External contact +1-202-555-1234 | MSISDN matches a Tecore MAS capture in housing block where I-12345 lives | 1.00 |
| External contact +1-202-555-1234 | visited inmate I-12345 5 days ago | 0.70 |

**Output:**
- Inmate I-12345 candidate score: **0.236** (audio + call signals)
- External contact +1-202-555-1234 candidate score: **0.495** (called +
  MSISDN match + visit)

→ HIGH-severity `drone_with_correlated_inmate` alert fires. Package goes
to SIU pager, warden email, and FBI liaison email. The complete evidence
trail (every event with timestamp and source) is attached.

This is what real DOC fusion-center workflows look like — combine weak
signals across multiple authorized data sources to produce a strong
inference about who orchestrated the drop.

---

## Configuration

`echo_cameras.yaml` is the single source of truth. Hot-reloadable —
the orchestrator picks up changes within 10s without restart.

Schema:
- `site` — facility metadata (timezone, lat/lng for bearing math)
- `zones` — named polygons / building tags with `permitted_hours` and
  `permitted_classifications`
- `cameras` — RTSP URL + capabilities (`has_audio`, `has_video`) +
  zone assignments
- `detection_overrides` — per-zone sensitivity tuning
- `alert_routing` — per-alert-type severity + channel list

Sample provided in the file with realistic Yard, Perimeter, Housing,
and Visitation zones.

---

## Alerts

Five named alert types, each routed to one or more channels via the YAML:

| Alert type | Default severity | Default channels |
|---|---|---|
| `drone_detected` | high | siu_pager, control_center_screen, email_alerts_distro |
| `inmate_out_of_bounds` | medium | control_center_screen |
| `violence_imminent` | critical | siu_pager, control_center_screen, all_officers_radio |
| `phone_in_inmate_hand` | medium | siu_pager, mas_correlation_engine |
| `drone_with_correlated_inmate` | critical | siu_pager, warden_email, fbi_liaison_email |

Channels:
- `email_alerts_distro`, `warden_email`, `fbi_liaison_email` — Gmail SMTP
- `siu_pager` — ntfy push to officer phones
- `control_center_screen`, `all_officers_radio`,
  `mas_correlation_engine` — log-only stubs by default; register custom
  channel handlers in `AlertDispatcher.register_channel()` for the
  agency's incident-management system, RTU integrations, etc.

---

## Required environment variables

For email/SMS alerts:
```
ECHO_SMTP_USER         your gmail address
ECHO_SMTP_PASS         a Gmail App Password (NOT your normal password)
ECHO_ALERT_TO          comma-separated recipients
```

For ntfy push:
```
ECHO_NTFY_TOPIC        topic name
ECHO_NTFY_TOKEN        bearer token (for private topics)
ECHO_NTFY_SERVER       default https://ntfy.sh
```

ViaPath, Tecore, and inmate-face-DB credentials are PLACEHOLDERs — see
`ARCHITECTURE.md` for the contracts each integration expects.

---

## What's runnable end-to-end TODAY

Without any vendor contracts, with just RTSP cameras:

- ✅ Multi-camera acoustic drone detection
- ✅ Per-camera audio score tracking, dashboard tiles
- ✅ Zone configuration + alert routing
- ✅ Correlation engine (will produce empty reports until other event
  sources are wired — but produces them correctly)
- ✅ Alert dispatch via email / SMS / ntfy
- ✅ Hot-reloadable config

What you GET with just RTSP + this codebase: a multi-camera acoustic
drone-detection system with rich alerting and a correlation engine
ready to ingest whatever data sources you wire in next.

What you'll ADD as integrations come online:
- Tecore MAS feed → drone events correlate with contraband-cellphone
  captures
- ViaPath feed → adds inmate calls, visits, deposits to the correlation
- YOLO drone model → adds visual confirmation that strengthens audio
  detection
- Facial recognition → adds inmate-location events for zone violations
  and correlation
- Each new feed makes every other one more valuable

This is intentional. Vendor contracts take months. Don't wait — deploy
the acoustic foundation today; light up the rest as the data feeds come
online.

---

## Honest limitations

- Acoustic detection has been validated on consumer/hobby quads and on
  speech/dog/wind rejection. It has NOT been validated against heavy-
  lift drones used in real correctional drops (DJI Matrice, Gustin
  custom builds, gas-powered). For a real deployment, expect to retrain
  the ML model on samples from your local threat picture.
- Vision + face + vendor integrations are scaffolds. They define the
  contracts but require real model weights, real face DBs, and real
  vendor APIs to function.
- Correlation engine weights (`DEFAULT_WEIGHTS` in `echo_correlation.py`)
  are heuristic priors. They should be tuned on real incident data
  once enough has accumulated.
- This is not FAA-authorized to disable / intercept drones. Detection
  + identification + alerting only.
- All facial recognition deployments require explicit agency-level
  policy authorization. See `ARCHITECTURE.md § Legal & policy`.
