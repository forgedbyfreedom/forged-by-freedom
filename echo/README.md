# ECHO — Acoustic Drone Detection + Correctional Security Platform

**One-line summary:** low-cost multi-modal detection, tracking, and
link-analysis for drone incursions — with fault-tolerant subsystem
health, an explicit pipeline state machine, and a fusion engine that
declines to guess when its sensors are down.

ECHO started as a single-microphone acoustic drone detector and has
grown into a full correctional facility platform combining:

- Multi-camera acoustic + visual drone detection
- LoRa / LoRaWAN SDR sniffer for sub-GHz control links that legacy
  counter-UAS misses
- Distributed acoustic sensor network (Ukraine Sky Fortress style) with
  TDOA position fusion
- Facial recognition, YOLO computer vision, zone rules
- Vendor connectors: ViaPath, Tecore MAS, Dedrone, Flock, SC DMV,
  Cellebrite, drone forensics
- CORTEX correlation / fusion engine with 25 weighted signals and
  health-aware inputs
- Explicit `IDLE → SCANNING → TRACKING → ALERT` pipeline state machine
- Operator dashboard with vis.js network graph + Leaflet drone map
- Optional FastAPI REST service for ops tooling and SIEMs

---

> ## Just received this in an email? Install in 60 seconds.
>
> 1. Save the `.tar.gz` attachment somewhere. Extract it:
>    - **macOS / Linux**: open Terminal → `tar xzf echo-correctional-full.tar.gz`
>    - **Windows**: right-click → 7-Zip / Extract All (Win 10+ has tar built in too)
>
> 2. From the extracted `echo/` folder, run the one-shot installer for your OS:
>    - **macOS / Linux**: `bash install.sh`
>    - **Windows**: right-click `install.ps1` → Run with PowerShell
>      (or `powershell -ExecutionPolicy Bypass -File install.ps1`)
>
> The installer auto-handles Python, ffmpeg, and dependencies. Takes
> about 60 seconds on a connected machine. Tells you exactly what to
> run next.
>
> If anything fails it prints the specific reason — paste that to
> whoever sent it.

---

## Two ways to use this codebase

**1. Single-microphone drone detector** — home / property / lab use.
Use `echo_dashboard.py`. Runs off a laptop mic or a single USB electret.
Not multi-camera, not link-analysis, not correlation. Just: "is there
a drone near me right now?" Suitable for personal defense installs and
any environment where the goal is detection, not investigation.

**2. Correctional facility platform** — multi-camera, multi-sensor,
link-analysis. Use `echo_multi.py` driven by `echo_cameras.yaml` and
`config.yaml`. This is the mode this repo has grown to serve. Runs on
a single deploy PC and scales to dozens of cameras + optional SDR +
optional distributed acoustic network. See [`ARCHITECTURE.md`](./ARCHITECTURE.md)
for the full system design and the SC-DOC-specific rollout plan.

Everything below defaults to describing the correctional platform.

---

## Quick start

### Single-mic mode
```bash
pip install -r requirements.txt
python echo_dashboard.py                    # live mic, http://127.0.0.1:5050
python echo_dashboard.py --wav file.wav     # analyze a WAV file
```

See [`ACOUSTIC_DETECTION_RESEARCH.md`](./ACOUSTIC_DETECTION_RESEARCH.md)
for the science: bandpass filtering, harmonic-stack scoring, persistence
tracking, ML confirmation.

### Correctional multi-camera mode
```bash
pip install -r requirements.txt

# 1. Edit echo_cameras.yaml — your camera RTSP URLs + zones
# 2. Edit config.yaml — tunables, health thresholds, optional API
# 3. Run the orchestrator
python echo_multi.py --config echo/echo_cameras.yaml

# In a second terminal, open the operator dashboard
python echo_correlation_dashboard.py --port 5060
# → http://127.0.0.1:5060

# Optional: run the FastAPI service (config.yaml api.enabled: true)
# It bootstraps automatically from echo_multi.py.
curl http://127.0.0.1:5058/status | jq .
```

**Demo mode** — no cameras, seeds synthetic events so you can
see what the dashboard looks like with realistic data:
```bash
python echo_correlation_dashboard.py --demo --port 5060
```

---

## Architecture at a glance

```
                    ┌───────────────────┐
                    │  Deploy PC (one)  │
                    └─────────┬─────────┘
                              │
     ┌────────────────────────┼──────────────────────────┐
     │                        │                          │
┌────▼────┐            ┌──────▼──────┐            ┌──────▼──────┐
│Cameras  │            │ Vendor      │            │ Sensors     │
│(RTSP)   │            │ connectors  │            │ (optional)  │
│         │            │             │            │             │
│ audio   │            │ ViaPath     │            │ LoRa SDR    │
│ vision  │            │ Tecore MAS  │            │ Lily Pads   │
│ face    │            │ Dedrone     │            │ (dist mic)  │
│         │            │ Flock LPR   │            │             │
│         │            │ SC DMV      │            │             │
│         │            │ Cellebrite  │            │             │
│         │            │ Forensics   │            │             │
└────┬────┘            └──────┬──────┘            └──────┬──────┘
     │                        │                          │
     │  every subsystem       │                          │
     │  reports health here → │                          │
     │            ┌───────────▼────────────┐             │
     │            │  echo_health.REGISTRY   │             │
     │            │  OK / DEGRADED / DOWN   │             │
     │            └───────────┬────────────┘             │
     │                        │                          │
     │  every subsystem       │                          │
     │  emits Events →        │                          │
     └────────────────────────┼──────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │      CORTEX        │
                    │ (echo_correlation) │
                    │                    │
                    │ - rolling window   │
                    │ - health-weighted  │
                    │ - min_viable check │
                    │ - 25 signals       │
                    └─────────┬──────────┘
                              │
                     ┌────────▼─────────┐
                     │  State machine   │
                     │  IDLE→SCAN→TRACK │
                     │  →ALERT          │
                     └────────┬─────────┘
                              │
              ┌───────────────┼────────────────┐
              │               │                │
    ┌─────────▼────┐  ┌───────▼──────┐  ┌──────▼───────┐
    │  Dashboard   │  │  Alerts      │  │  FastAPI     │
    │  (Flask +    │  │  (email/SMS/ │  │  (optional)  │
    │   vis.js +   │  │   ntfy +     │  │              │
    │   Leaflet)   │  │   channels)  │  │              │
    └──────────────┘  └──────────────┘  └──────────────┘
```

Design principle: **fail loud into the registry, silent to the
pipeline**. A camera going down lights up the dashboard but does
not break the other cameras or the correlation engine.

---

## Module map

```
echo/
├── echo_engine.py                    OK  acoustic detection (BPF, harmonics, persistence, ML)
├── echo_ml.py                        OK  numpy-only MLP for drone confirmation
├── echo_alerts.py                    OK  multi-channel alert dispatch (email/SMS/ntfy + named routing)
├── echo_dashboard.py                 OK  Flask SSE single-mic dashboard (original)
├── echo_rtsp.py                      OK  RTSP audio ingestion via ffmpeg
├── echo_cameras.yaml                 OK  multi-camera + zones + alert-routing config
├── echo_zones.py                     OK  inmate access rules (hours, classification, movement)
├── echo_correlation.py               OK  CORTEX — rolling event log + 25-signal fusion engine
│                                          with health-aware inputs + min_viable_sensors guard
├── echo_correlation_dashboard.py     OK  operator-facing Flask dashboard
├── echo_multi.py                     OK  orchestrator: ties every camera + integration together
│
│  ── Fault tolerance + lifecycle ─────────────────────────────
├── echo_health.py                    OK  HealthRegistry (OK/DEGRADED/DOWN/UNKNOWN)
│                                          + safe_loop() isolated exception handling
├── echo_state.py                     OK  PipelineStateMachine (IDLE→SCANNING→TRACKING→ALERT)
│
│  ── Configuration + operations ──────────────────────────────
├── echo_config.py                    OK  layered config loader
├── config.yaml                       OK  every tunable in one file
├── echo_api.py                       OK  optional FastAPI (/status /detections /scan /health
│                                          /subsystems /state /reports/recent)
│
│  ── Sub-GHz + distributed sensing ───────────────────────────
├── echo_lora.py                      ··  PLACEHOLDER — LoRa/LoRaWAN SDR sniffer
│                                          (sub-GHz drone control link — home-built drop rigs /
│                                           ExpressLRS-900 that 2.4 GHz-tuned counter-UAS misses)
├── echo_lily_pads.py                 OK  distributed acoustic sensor network + TDOA fusion
│                                          (Ukraine Sky Fortress-style; ~$140 Pi nodes)
│
│  ── Vendor + agency integrations (PLACEHOLDERS) ────────────
├── echo_vision.py                    ··  YOLO (drone / phone-in-hand / violence)
├── echo_face.py                      ··  committee's in-house facial recognition
├── echo_dedrone.py                   ··  Dedrone multi-sensor + serial-number tracks
├── echo_flock.py                     ··  Flock Safety LPR network
├── echo_dmv_sc.py                    ··  SC DMV / SLED plate → owner (DPPA-compliant)
├── echo_cellebrite.py                ··  UFDR forensic extraction ingestion
├── echo_drone_forensics.py           ··  recovered-airframe data (flight log, pairing, media)
├── echo_viapath.py                   ··  ViaPath / GTL / IRT (calls, tablet, visit, deposit)
├── echo_tecore.py                    ··  Tecore MAS contraband-phone capture
│
│  ── Docs ───────────────────────────────────────────────────
├── CALIBRATION.md                        step-by-step field-tuning + safe ranges + spectrogram guide
├── ARCHITECTURE.md                       full system design + procurement + legal
├── INTEGRATION_CHECKLIST.md              committee deliverable — vendor wiring
├── ACOUSTIC_DETECTION_RESEARCH.md        the science behind the audio detector
└── README.md                             this file
```

`OK` = runnable today.  `··` = scaffold with `# PLACEHOLDER` markers +
top-of-file `# TO COMPLETE — committee must provide:` checklist.

---

## Subsystem health & fault tolerance

Every subsystem — cameras, LoRa SDR, Lily Pad hub, vendor connectors —
reports one of four statuses to the shared `HealthRegistry`
(`echo_health.py`):

| Status    | Meaning                                       | CORTEX behavior            |
|-----------|-----------------------------------------------|----------------------------|
| `OK`      | Producing valid data, no recent errors        | Full weight                |
| `DEGRADED`| Producing with warnings / retries / partial   | Full weight, flagged       |
| `DOWN`    | Not producing — errors, disconnected, crashed | **Signals dropped**        |
| `UNKNOWN` | Never came up (subsystem disabled)            | Signals dropped            |

Two isolation guarantees:

1. **`safe_loop()`** — subsystem main loops run inside a wrapper that
   catches exceptions, reports DEGRADED after 3 consecutive errors and
   DOWN after 10, then retries with backoff. Exceptions never escape.
2. **Stale-timeout auto-demotion** — a subsystem that hasn't reported
   OK for `health.stale_timeout_sec` (default 60) auto-demotes to DOWN
   even if it hasn't thrown. Prevents silent hangs.

CORTEX consults the registry on every correlation pass:
- Signals from DOWN / UNKNOWN sources are **dropped**.
- The report's `subsystem_health`, `contributing_subsystems`, and
  `dropped_subsystems` fields show operators exactly whose data
  drove the score.
- If fewer than `correlation.min_viable_sensors` subsystems contributed,
  the report comes back `decision_declined=True` with a reason string
  rather than guessing from thin data.

Live status: `curl http://127.0.0.1:5058/subsystems` (if the API is on).

---

## Pipeline state machine

ECHO uses an explicit four-state lifecycle. Every transition is
logged with timestamp / from → to / trigger / event id, and pushed
onto a bounded history ring buffer.

```
    ┌────────┐  drone signal ≥ floor    ┌───────────┐
    │  IDLE  │────────────────────────▶│  SCANNING │
    └────────┘                         └───────────┘
        ▲                                 │      ▲
        │ scan_timeout / no signal        │      │ signal fades
        │                                 ▼      │
        │                             ┌──────────┴──┐
        │                             │  TRACKING   │
        │                             └──────────┬──┘
        │                                        │ correlation ≥ ALERT floor
        │                                        ▼
        │                                    ┌───────┐
        └────────────────── ack ─────────────┤ ALERT │
                                             └───────┘
```

| From      | Legal → next                     |
|-----------|----------------------------------|
| IDLE      | SCANNING                         |
| SCANNING  | IDLE, TRACKING, ALERT            |
| TRACKING  | SCANNING, ALERT                  |
| ALERT     | TRACKING, SCANNING, IDLE (ack)   |

Invalid transitions raise `InvalidTransition`; the `try_transition()`
variant silently no-ops instead. `bind_to_correlation_engine()`
auto-drives the machine: drone events transition IDLE → SCANNING →
TRACKING, and a correlation report scoring at or above
`correlation.alert_score_floor` promotes to ALERT.

Live state: `curl http://127.0.0.1:5058/state?history_limit=20` (API on).

---

## Configuration — layered, hot-friendly

Precedence (later overrides earlier):

1. Baked defaults in `echo_config.DEFAULTS`
2. `config.yaml` next to the code (or `$ECHO_CONFIG` if set)
3. `ECHO_*` environment variables — nested with `__`
4. Per-run overrides passed to `echo_config.load(overrides={...})`

```bash
# Field-debug pattern — try a tweak without editing files:
ECHO_DETECTOR__HARMONIC_SNR_DB=10 \
ECHO_CORRELATION__MIN_VIABLE_SENSORS=3 \
python echo_multi.py --config echo/echo_cameras.yaml
```

Full knob reference: [`CALIBRATION.md`](./CALIBRATION.md).

`echo_cameras.yaml` is the operational config — cameras, zones,
alert routing. Hot-reloadable — the orchestrator picks up changes
within 10 s without restart.

`config.yaml` is the tuning config — thresholds, weights, health
timeouts, API port. Loaded once at startup; edit + restart to change.

---

## REST API

Optional, off by default. Enable in `config.yaml`:

```yaml
api:
  enabled: true
  host: 127.0.0.1
  port: 5058
  bearer_token: null       # REQUIRED if host != 127.0.0.1
```

Endpoints (bearer auth required for non-loopback):

| Method | Path                     | Purpose                                          |
|--------|--------------------------|--------------------------------------------------|
| GET    | `/health`                | Liveness (no auth) — returns 200 if alive        |
| GET    | `/status`                | Pipeline uptime + config + subsystem counts      |
| GET    | `/subsystems`            | Full HealthRegistry snapshot + counts by status  |
| GET    | `/state?history_limit=`  | Pipeline state + transition history              |
| GET    | `/detections?since=…&source=…&limit=…` | Ring buffer of recent events      |
| GET    | `/reports/recent?limit=` | Last N CorrelationReports                        |
| POST   | `/scan`                  | Fire a synthetic drone event — trigger a scan    |

Point your SIEM at `/detections?since=…` on a poll; wire your Slack
bot at `/status`; put `/health` in your load balancer.

---

## Alerts

Named alert types routed to one or more channels via YAML:

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
- `control_center_screen`, `all_officers_radio`, `mas_correlation_engine`
  — log-only stubs by default; register custom channel handlers in
  `AlertDispatcher.register_channel()` for the agency's incident-management
  system, RTU integrations, etc.

---

## Required environment variables

For email alerts:
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

Vendor credentials — ViaPath, Tecore, Dedrone, Flock, DMV, Cellebrite —
are PLACEHOLDERs. Each connector documents the credentials it wants at
the top of its file; the committee fills them in via
[`INTEGRATION_CHECKLIST.md`](./INTEGRATION_CHECKLIST.md).

---

## Data sources → correlation signals — full reference

CORTEX fuses **25 weighted signals**. Each subsystem contributes zero
or more; DOWN subsystems contribute nothing regardless.

### Inmate signals (who inside caused / received the drop)

| Signal | Default weight | Data source |
|---|---:|---|
| `inmate_outdoors_at_drone_time` | 0.14 | Face + zone |
| `inmate_on_phone_at_drone_time` | 0.12 | ViaPath |
| `inmate_phone_in_hand_visual`   | 0.14 | YOLO vision |
| `inmate_mas_capture_correlation`| 0.14 | Tecore MAS |
| `inmate_recent_visitor_contact` | 0.06 | ViaPath |
| `inmate_recent_deposit_anomaly` | 0.06 | ViaPath |
| `inmate_history`                | 0.04 | Case history |
| `inmate_zone_violation`         | 0.06 | Zones + face |
| `inmate_pan_called_by_seized_phone` | 0.16 | Cellebrite |
| `inmate_cellebrite_msg_thread`  | 0.10 | Cellebrite |

### External-contact signals (who orchestrated from outside)

| Signal | Default weight | Data source |
|---|---:|---|
| `contact_called_inmate_pre_drop`     | 0.22 | ViaPath |
| `contact_visited_recently`           | 0.10 | ViaPath |
| `contact_deposited_recently`         | 0.10 | ViaPath |
| `contact_known_associate`            | 0.14 | Case history |
| `contact_msisdn_matches_mas`         | 0.20 | Tecore MAS |
| `contact_plate_at_perimeter`         | 0.16 | Flock LPR |
| `contact_plate_hotlist`              | 0.10 | Flock NCIC |
| `contact_dmv_owner_in_viapath`       | 0.18 | SC DMV |
| `contact_cellebrite_location_near`   | 0.20 | Cellebrite |
| `contact_cellebrite_drone_app`       | 0.18 | Cellebrite |

### Drone-centric signals (boost drone-event confidence)

| Signal | Default weight | Data source |
|---|---:|---|
| `drone_dedrone_confirmed`            | 0.30 | Dedrone |
| `drone_serial_known`                 | 0.40 | Dedrone Remote-ID |
| `drone_serial_matches_recovery`      | 0.50 | Drone forensics |
| `drone_lora_link_detected`           | 0.22 | LoRa SDR |
| `drone_lora_bearing_toward_facility` | 0.28 | KrakenSDR DF |

**Tuning philosophy:** don't change weights blindly. Run at defaults for
30 days, label reports (real / false / unresolved), then A/B a
challenger `config.yaml`. See CALIBRATION.md § "Retuning correlation
weights" for the workflow.

---

## Worked example — link analysis in action

A drone is detected over Yard A at 14:32:15 by `cam-yard-east`'s
microphone. CORTEX immediately runs against the past 4 hours of events
across every wired-in data source.

**Drone-centric corroborating signals:**

| Signal | Score | Source |
|---|---|---|
| Dedrone confirmed track ±30 s | 1.00 | Dedrone fusion |
| Drone serial captured (DJI Remote ID) | 1.00 | Dedrone RF |
| ⭐⭐ Serial matches previously-recovered airframe SIU-2026-0078 | 1.00 | Drone forensics |
| LoRa chirp ELRS-900 @ 915.5 MHz, RSSI -78 dBm | 1.00 | LoRa SDR |

**Per-subject signals:**

| Subject | Signal | Score |
|---|---|---|
| Inmate I-12345 | seen on cam-yard-east 2 min before drone (face) | 0.60 |
| Inmate I-12345 | on ViaPath call 1 min before drone | 0.80 |
| External contact +1-843-555-1234 | called inmate 1 min before drone | 0.97 |
| External contact +1-843-555-1234 | MSISDN matches Tecore MAS capture in inmate's housing block | 1.00 |
| External contact +1-843-555-1234 | DMV owner appears in ViaPath visit records | 1.00 |
| External contact +1-843-555-1234 | Cellebrite extraction shows DJI Fly app installed | 1.00 |
| External contact (Flock plate ABC1234) | vehicle passed perimeter 1 min before drone | 0.97 |

**Output:**
- External contact candidate score: **0.77** (called + DMV + MAS + Cellebrite)
- Inmate candidate score: **0.24** (face + call)
- Drone identified as SAME PHYSICAL AIRFRAME used in prior incident

**Subsystem health at report time (`subsystem_health`):**
- All 12 contributing subsystems: OK
- 0 dropped
- Not declined

→ Critical `drone_with_correlated_inmate` alert fires. Package goes to
SIU pager, warden email, FBI liaison email. Full evidence trail (every
event with timestamp + source + raw payload reference) is attached.

The state machine transitions `SCANNING → ALERT` on this report; it
stays ALERT until an operator acks via the dashboard or the auto-ack
timeout expires (default: never).

---

## Sub-GHz / SDR — `echo_lora.py`

LoRa / LoRaWAN and ExpressLRS-900 live in the 902-928 MHz US ISM band,
which most 2.4 / 5.8 GHz-tuned counter-UAS (Dedrone RfPatrol, most
legacy) doesn't cover. `echo_lora.py` closes that gap with a
CSS-preamble sniffer:

- Minimum viable: RTL-SDR Blog V4 + ANT500 whip (~$65 total)
- Recommended: HackRF One (~$400) for full-band capture
- Professional / DF: KrakenSDR 5-channel coherent array (~$680)
- Passive receive only by default; transmit / jamming gated behind
  FCC authorization (federal facilities can obtain; state generally
  cannot without legislation)
- Two new correlation signals: `drone_lora_link_detected` (any chirp
  ±90 s of a drone event) and `drone_lora_bearing_toward_facility`
  (KrakenSDR bearing intersects perimeter)
- Facility whitelist so legitimate 900 MHz emitters (AMR meters, staff
  radios) don't false-alarm

See [`INTEGRATION_CHECKLIST.md`](./INTEGRATION_CHECKLIST.md) § 5g for
the hardware / install fields the RF tech fills in.

---

## Distributed acoustic sensing — `echo_lily_pads.py`

Inspired by Ukraine's Sky Fortress program: many low-cost networked
microphones spread across (and around) a facility, each running the
same `echo_engine.py` detector, with a central hub running TDOA fusion
to produce facility-scale (x, y, z) drone tracks.

- Per-node cost: ~$140 (basic Pi + USB mic) to ~$500 (pro-grade)
- 20 nodes at ~$140 each = ~$3k for full facility coverage
- GPS PPS clock sync (best) → PTP over PoE → NTP → ultrasonic beacon
  fallback documented
- TDOA hyperbolic-position solver with weighted-least-squares fit
- Emits high-confidence `drone_audio` events tagged `source_kind:
  lily_pad_tdoa` so the dashboard plots them distinctly

**Preferred SC-DOC install — net-pole perimeter arrays.** Every major
SC-DOC institution already has driving-range-style netting on tall
poles around the perimeter to intercept throw-overs. Those poles
are ideal Lily Pad mounts: already tall (30-60 ft, well above ground
wind noise), already spaced regularly (20-40 ft), often already
electrified, and physically outside the containment wall so mics face
outward and catch drones on approach. Use
`echo_lily_pads.net_pole_perimeter_array()` to generate the node list
from a surveyed perimeter polygon. Per-pole BOM is ~$350 (Pi 5 +
6-mic array + GPS PPS + PoE + weatherproof + windscreen + surge). See
[`CALIBRATION.md`](./CALIBRATION.md) § "Net-pole perimeter arrays"
for install specifics.

See [`INTEGRATION_CHECKLIST.md`](./INTEGRATION_CHECKLIST.md) § 5h for
the deployment fields (node hardware tier, install locations,
transport, retention, federation policy).

---

## What's runnable end-to-end TODAY

Without any vendor contracts, with just RTSP cameras:

- ✅ Multi-camera acoustic drone detection
- ✅ Per-camera health tracking with automatic DEGRADED / DOWN reporting
- ✅ Zone configuration + alert routing
- ✅ CORTEX correlation engine (produces reports; will emit
  `decision_declined` until 2+ subsystems are live)
- ✅ Pipeline state machine driving IDLE → SCANNING → TRACKING → ALERT
- ✅ Alert dispatch via email / SMS / ntfy
- ✅ Optional FastAPI REST service
- ✅ Layered config with env-var overrides
- ✅ Full operator dashboard (link-analysis graph + drone map)

What you'll add as integrations come online:
- Tecore MAS feed → drone events correlate with contraband-cellphone captures
- ViaPath feed → adds inmate calls, visits, deposits to correlation
- YOLO drone model → visual confirmation strengthens audio detection
- Facial recognition → adds inmate-location events for zone violations
- LoRa SDR → catches sub-GHz control links Dedrone misses
- Lily Pads → facility-wide TDOA position tracking

Each feed makes every other one more valuable. Vendor contracts take
months — deploy the acoustic foundation today; light up the rest as
data feeds come online.

---

## Where to look next

- **Tuning a new install** → [`CALIBRATION.md`](./CALIBRATION.md)
- **Wiring vendor integrations** → [`INTEGRATION_CHECKLIST.md`](./INTEGRATION_CHECKLIST.md)
- **Full architecture + legal** → [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- **Acoustic detection science** → [`ACOUSTIC_DETECTION_RESEARCH.md`](./ACOUSTIC_DETECTION_RESEARCH.md)

---

## License / usage

This is a defense-oriented platform built for authorized correctional
security use. Facial recognition, license-plate lookup, mobile forensic
ingestion, and RF surveillance carry serious legal obligations
(DPPA, CFAA, ECPA, state wiretap and biometric laws, agency policy).
Every vendor integration ships as a scaffolded placeholder specifically
so the deploying agency can wire it up under its own legal review.

Do not deploy any component of ECHO in a facility without a signed
authorization, a documented retention policy, and an operator
training program.
