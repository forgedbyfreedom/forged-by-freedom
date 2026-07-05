# ECHO — Correctional Drone & Inmate Monitoring Architecture

This document describes the full system design for ECHO as a correctional
drone-incursion + inmate-monitoring + link-analysis platform.

> **Reading order:** Capabilities → Data flow → Per-module status →
> Vendor integration paths → Legal & policy → Deployment.

---

## Capabilities (current and planned)

| # | Capability | Status | Implementing module |
|---|---|---|---|
| 1 | Live acoustic drone detection (single mic) | ✅ Runnable today | `echo_engine.py`, `echo_ml.py` |
| 2 | Live acoustic drone detection (multi-camera, RTSP) | ✅ Runnable today | `echo_rtsp.py`, `echo_multi.py` |
| 3 | Per-camera audio score, dashboard tiles | ✅ Runnable | `echo_dashboard.py` (extend), `echo_multi.py` |
| 4 | Zone-based inmate access rules + out-of-bounds alerts | ✅ Runnable logic (needs face events) | `echo_zones.py` |
| 5 | Drone visual detection (YOLO) | 🟡 Scaffold + stub | `echo_vision.py` |
| 6 | Cellphone-in-inmate-hand visual detection (YOLO) | 🟡 Scaffold + stub | `echo_vision.py` |
| 7 | Pre-violence behavior detection (temporal model) | 🟡 Scaffold + stub | `echo_vision.py` |
| 8 | Inmate facial recognition | 🟡 Scaffold + stub | `echo_face.py` |
| 9 | ViaPath / GTL / IRT data ingestion | 🟡 Scaffold + stub (needs vendor contract) | `echo_viapath.py` |
| 10 | Tecore MAS data ingestion | 🟡 Scaffold + stub (needs vendor contract) | `echo_tecore.py` |
| 11 | Cross-system link analysis & correlation | ✅ Runnable — accepts whatever events arrive | `echo_correlation.py` |
| 12 | Named-alert multi-channel dispatch | ✅ Runnable | `echo_alerts.py` |
| 13 | Hot-reloadable YAML config | ✅ Runnable | `echo_cameras.yaml`, `echo_multi.py` |

**Legend:**
- ✅ Runnable today — works end-to-end as written
- 🟡 Scaffold + stub — interface is real, integration points clearly marked `# PLACEHOLDER`, fills in when external dependencies become available

---

## Data flow

```
┌─────────────────────┐
│   Valerus / ONVIF   │
│  cameras (RTSP)     │
└────────┬────────────┘
         │ rtsp://
         │
   ┌─────▼──────────────────────────────────────────────────┐
   │   echo_rtsp.py — one RtspAudioSource per camera        │
   │   ffmpeg subprocess: RTSP → 16 kHz mono PCM blocks     │
   └─────┬──────────────────────────┬───────────────────────┘
         │ audio blocks             │ JPEG frames (on demand)
         ▼                          ▼
   ┌──────────────────┐    ┌─────────────────────┐
   │  echo_engine.py  │    │   echo_vision.py    │ ── PLACEHOLDER
   │  acoustic        │    │   YOLO inference    │
   │  detection       │    │   • drones          │
   │  (existing)      │    │   • phones-in-hand  │
   └────────┬─────────┘    │   • violence        │
            │              └─────┬───────────────┘
            │                    │
            │                    │
            │              ┌─────▼───────────────┐
            │              │   echo_face.py      │ ── PLACEHOLDER
            │              │   facial recog vs   │
            │              │   inmate DB         │
            │              └─────┬───────────────┘
            │                    │ InmateLocation events
            │                    ▼
            │              ┌─────────────────────┐
            │              │   echo_zones.py     │
            │              │   out-of-bounds     │
            │              │   / time / class    │
            │              └─────┬───────────────┘
            │                    │ ZoneViolation events
            │                    │
            ▼                    ▼
   ┌────────────────────────────────────────────────────┐
   │   echo_correlation.py — rolling event log +        │
   │   on-demand correlation pass                       │
   │                                                    │
   │   Inputs from ALL modules:                         │
   │     • drone_audio    (echo_engine)                 │
   │     • drone_visual   (echo_vision)                 │
   │     • vision_phone   (echo_vision)                 │
   │     • vision_violence(echo_vision)                 │
   │     • face           (echo_face)                   │
   │     • zone_violation (echo_zones)                  │
   │     • viapath_call   (echo_viapath ── PLACEHOLDER) │
   │     • viapath_tablet (echo_viapath ── PLACEHOLDER) │
   │     • viapath_visit  (echo_viapath ── PLACEHOLDER) │
   │     • viapath_deposit(echo_viapath ── PLACEHOLDER) │
   │     • mas_capture    (echo_tecore  ── PLACEHOLDER) │
   │                                                    │
   │   Output: CorrelationReport per drone detection    │
   │     • ranked inmate candidates with score breakdown│
   │     • ranked external-contact candidates           │
   │     • full evidence trail (every contributing event)│
   └────────────────────┬───────────────────────────────┘
                        │
                        ▼
              ┌────────────────────────┐
              │   echo_alerts.py       │
              │   AlertDispatcher      │
              │   per-type, multi-     │
              │   channel routing      │
              └────────────────────────┘
```

---

## Per-module status & contract

### `echo_rtsp.py` — ✅ Runnable
RTSP audio ingestion. ffmpeg subprocess pulls audio from any RTSP URL,
yields 0.5-second 16 kHz mono float32 numpy blocks via callback.
Auto-reconnects with exponential backoff (capped 60s). One source per
camera. Also has `grab_jpeg_frame()` for on-demand still capture.

### `echo_zones.py` — ✅ Runnable
Loads zones from YAML, evaluates `InmateLocation` events against:
- `permitted_hours` per zone
- `permitted_classifications` per zone (GP, GP-low, AdSeg, etc.)
- Scheduled-movement overrides (PLACEHOLDER for inmate scheduling API)

Emits `ZoneViolation` events into the correlation engine + dispatches
`inmate_out_of_bounds` alerts.

### `echo_vision.py` — 🟡 PLACEHOLDER (interface complete, no model)
**To fill in**, install YOLO/Ultralytics + your trained weights:
```bash
pip install ultralytics opencv-python torch torchvision
```
Then in `VisionWorker._load_models()`, load your `.pt` files:
- Drone detector: pretrained on Roboflow's drone dataset, OR fine-tuned on
  your local threat picture
- Phone detector: COCO has a "cell phone" class but performs poorly on
  prison surveillance; fine-tune on local footage
- Violence detector: SlowFast / MoViNet (single-frame YOLO won't do this)

### `echo_face.py` — 🟡 PLACEHOLDER (interface complete, no model + DB)
**To fill in**:
- Install InsightFace or DeepFace
- Build inmate face DB from the agency's existing intake-photo system
  (5-15 photos per inmate; embeddings stored in FAISS / Qdrant / Pinecone)
- Implement `FaceRecognitionWorker.process_frame()`

**Legal pre-reqs** (also see `### Legal & policy` below):
- Agency policy authorizes biometric ID of inmates
- Intake-photo dataset is authorized for FR use
- Staff/visitor face redaction policy is in place

### `echo_viapath.py` — 🟡 PLACEHOLDER (interface complete, no API client)
ViaPath Technologies (formerly Global Tel*Link / GTL, rebranded 2022)
runs inmate phone, tablet, IRT, video visitation, and ConnectNetwork
deposits. Single vendor, multiple data streams. **Procurement required:**
- Active ViaPath contract at the facility
- Signed data-sharing addendum
- ViaPath admin with API credentials
- Sometimes Letter of Authority from warden / state DOC

Integration paths (any of):
- REST API (newer deployments, JSON over HTTPS)
- SFTP daily/hourly CSV drops (most state DOCs still on this)
- Direct SQL read-replica access (largest facilities only)

### `echo_tecore.py` — 🟡 PLACEHOLDER (interface complete, no API client)
Tecore Networks Managed Access System (MAS). Captures every
unauthorized cellphone that powers on inside the facility's RF
footprint. **Procurement required:**
- Active Tecore MAS deployment
- Signed data-sharing addendum
- Coordination with FCC-licensed RF coordinator (MAS operates under
  FCC special temporary authority)
- Sometimes state-level approval

Integration paths:
- REST API (newer MAS deployments)
- Syslog-over-TLS (real-time event stream)
- SFTP daily CSV drops (legacy)

### `echo_correlation.py` — ✅ Runnable
Heart of the link-analysis system. Rolling 4-hour event log (configurable),
indexed by source, inmate_id, msisdn. On every drone event, runs a
weighted-multi-signal correlation pass producing a `CorrelationReport`
with ranked inmate candidates and external-contact candidates.

Signals (each scored 0..1, weighted; weights in `DEFAULT_WEIGHTS`):

**Inmate signals**
- `inmate_outdoors_at_drone_time` (0.18)
- `inmate_on_phone_at_drone_time` (0.16)
- `inmate_phone_in_hand_visual` (0.18)
- `inmate_mas_capture_correlation` (0.18)
- `inmate_recent_visitor_contact` (0.08)
- `inmate_recent_deposit_anomaly` (0.08)
- `inmate_history` (0.06)
- `inmate_zone_violation` (0.08)

**External-contact signals**
- `contact_called_inmate_pre_drop` (0.30)
- `contact_visited_recently` (0.15)
- `contact_deposited_recently` (0.15)
- `contact_known_associate` (0.20)
- `contact_msisdn_matches_mas` (0.20)  ← strongest single signal

### `echo_multi.py` — ✅ Runnable
Top-level orchestrator. Loads YAML config, spins up per-camera bundles
(EchoEngine + RtspAudioSource + VisionWorker + FaceRecognitionWorker),
manages lifecycle, hot-reloads config every 10s. Wires every event
source into the correlation engine.

### `echo_alerts.py` — ✅ Runnable
Named-alert dispatcher with per-type channel routing from YAML. Built-in
channels: email (Gmail SMTP), SMS (carrier email-to-text gateway), ntfy
push. Custom channels (siu_pager, control_center_screen, warden_email,
fbi_liaison_email, mas_correlation_engine) registered via
`register_channel()`.

---

## Vendor integration paths (procurement priorities)

Order of value-per-effort if you're building this for a real facility:

1. **RTSP from existing cameras** — Free. Already in this codebase. Get
   credentials from Vicon Valerus / ONVIF / etc. and you're running.
2. **Inmate intake photo DB** — Free (you already have it). Required for
   facial recognition. Pull from existing JMS/OMS.
3. **YOLO drone model** — Free pre-trained options exist. Cost:
   ~$5-10k of focused engineering work to fine-tune on your specific
   drone threat picture.
4. **Tecore MAS data feed** — If you ALREADY have a Tecore MAS
   deployment, this is essentially free (just data-sharing paperwork).
   If you don't have MAS yet, deployment is ~$200k-1M+ depending on
   facility size.
5. **ViaPath data feed** — ViaPath is at virtually every US facility
   already. Cost is the data-sharing contract, not new deployment.
   Talk to your account rep.
6. **Visitation system** — Usually inside ViaPath, same as above. If
   you use a separate visitation vendor (Securus, ICSolutions), wire
   that vendor's API instead.
7. **YOLO phone-in-hand + violence models** — Each is a 2-4 week
   ML engineering project requiring local training data.

---

## Legal & policy requirements

This section is not legal advice. Coordinate with the agency's general
counsel before deploying any of:

1. **Facial recognition of inmates** — Legal in most US jurisdictions.
   Policy at the agency level should explicitly authorize biometric ID
   from cameras. Logs of every identification are discoverable.
2. **Facial recognition of staff or visitors** — Different legal
   regime. Staff have employment-contract considerations. Visitors have
   civilian privacy rights and many states require posted notice +
   consent. By default, `echo_face.py` redacts non-inmate faces without
   generating embeddings.
3. **Voice biometric ID of inmate-phone parties** — ViaPath IRT supports
   this on paid tiers. Same considerations as FR.
4. **Tecore MAS operation** — Operates under FCC special temporary
   authority. RF coordinator at the agency must coordinate with carriers.
5. **Cross-system link analysis** — Combines multiple authorized data
   feeds. The act of combining is generally legal where each feed is
   authorized. Maintain audit logs of every correlation run.
6. **Drone identification and tracking** — Detecting drones is legal
   everywhere. Disabling / intercepting them is regulated under FAA +
   federal law and generally restricted to specific federal agencies
   (DOJ / DHS), not state DOCs.
7. **Records retention** — Every event in the correlation engine is
   discoverable. Set explicit retention policies; default
   `CorrelationEngine.window` is 4 hours of in-memory rolling log,
   intentionally short. Long-term storage requires a separate
   evidence-management workflow with chain-of-custody.

---

## Deployment

### Hardware
Realistic per-facility specs:
- 1× server, Linux (Ubuntu 22.04+) or Windows Server 2022+
- NVIDIA GPU with ≥ 16 GB VRAM (RTX 4070/4080/A4000 or better) — for
  YOLO on multiple streams + face recognition
- 32+ GB RAM
- 1 Gbps NIC on the camera VLAN
- 2+ TB SSD (rolling video buffer for evidence)

### Network
- ECHO server on the same VLAN as cameras, or with explicit routing
- Separate VLAN for ViaPath integration (most agencies require)
- Tecore MAS data feed typically via syslog-over-TLS to ECHO server
- Outbound HTTPS for OTA model updates (optional, can be air-gapped)

### Software
- Python 3.11+
- ffmpeg (for RTSP)
- PyTorch + Ultralytics (for YOLO, when added)
- InsightFace + FAISS (for face recognition, when added)
- See `echo/requirements.txt` for current pin set

### Run
```bash
cd echo
pip install -r requirements.txt
python echo_multi.py --config echo_cameras.yaml
```

The orchestrator binds to no ports by itself; pair with
`echo_dashboard.py` (extends to multi-camera tiles + correlation feed)
for the operator UI.

---

## Roadmap / next steps

**Immediately doable (no vendor dependencies)**
- Fine-tune drone-detection YOLO on local threat picture footage
- Build inmate-face DB from agency JMS intake photos
- Implement `_inmate_has_scheduled_authorization()` against agency
  scheduling system

**Blocked on vendor contracts**
- ViaPath data-sharing addendum → fills in `echo_viapath.py`
- Tecore data-sharing addendum → fills in `echo_tecore.py`

**Future**
- Multi-facility deployment (one orchestrator coordinates several sites)
- ML-driven adaptive threshold tuning per camera based on false-positive
  rate
- Voice biometric matching at correlation time (caller voice ≅ known
  external contact)
- Geographic IP-to-physical mapping for video-visit IPs (correlate to
  drone-drop pickup vehicle if seen on perimeter)
