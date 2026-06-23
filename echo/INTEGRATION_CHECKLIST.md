# ECHO Integration Checklist — for the committee

Single source of truth for what the committee needs to provide so ECHO
can move from "scaffold with PLACEHOLDERs" to "production code wired to
your real systems."

Status legend per item:
- 🟢 filled in / ready
- 🟡 partial information
- ⚪ blank — committee fills in
- 🚫 explicitly out of scope

---

## Section 1 — Deployment target (work AI PC)

| Item | Committee answer |
|---|---|
| Hostname or IP | ⚪ |
| OS + version | ⚪ (Windows Server / Ubuntu / Rocky?) |
| GPU model + VRAM | 🟡 RTX 3090 or 4090 — confirm which |
| Total RAM | 🟢 128 GB |
| Network access route from outside the facility | ⚪ Twingate? Site-to-site VPN? AnyConnect? |
| Disk space available | ⚪ (~500 GB recommended for rolling video buffer + face DB + model weights) |
| Existing services on this box (port-collision check) | ⚪ |

---

## Section 2 — Cameras (Valerus)

| Item | Committee answer |
|---|---|
| Valerus version | ⚪ |
| Number of cameras | ⚪ |
| Camera types (have-mic vs. video-only) | ⚪ |
| RTSP URLs available directly per camera? (preferred) OR must go through Valerus VMS API? | ⚪ |
| Vicon SDK access if needed | ⚪ |
| Credentials handling — committee-managed cert/key, or per-camera user/pass? | ⚪ |
| Sample RTSP URL for one test camera (we'll tune against this one first) | ⚪ |

**Module impacted:** `echo_rtsp.py` (already runnable; just needs URLs)

---

## Section 3 — Facial recognition (committee's in-house system)

| Item | Committee answer |
|---|---|
| **Integration mode** — REST / Python library / gRPC / file-watcher | ⚪ |
| Endpoint URL OR import path OR gRPC stub OR watched directory | ⚪ |
| Auth — bearer token / mTLS / API key / IP allowlist | ⚪ |
| Where do credentials live (secrets manager / .env / vault)? | ⚪ |
| Request payload — what frame format? (JPEG / PNG / raw RGB / base64) | ⚪ |
| Response payload — schema example for a "match" record | ⚪ |
| Response payload — schema example for a "non-match" record | ⚪ |
| Does the FR system already redact staff/visitor faces? | ⚪ |
| Latency SLO per identify() call | ⚪ |
| Throughput SLO (sustained calls/sec) | ⚪ |

**Module impacted:** `echo_face.py` — once answered, only `FaceRecognitionClient._call_committee_fr()` changes.

---

## Section 4 — Tecore MAS (contraband cellphone capture)

| Item | Committee answer |
|---|---|
| Tecore iNAC / MAS version | ⚪ |
| **Integration mode** — REST / syslog-over-TLS / SFTP CSV | ⚪ |
| Endpoint URL / syslog listen-port / SFTP host+path | ⚪ |
| Auth — API key / mTLS cert / SFTP key | ⚪ |
| Field mapping confirmation vs `MasCaptureEvent` (timestamp, imei, imsi, msisdn, rf_cell_id, attempted_action, destination, blocked, signal_strength_dbm, first_seen_at_facility) | ⚪ |
| RF cell → housing block mapping table | ⚪ |
| Sample capture event (sanitized JSON / CSV row) | ⚪ |
| Poll interval (REST) / file-drop schedule (SFTP) | ⚪ |

**Module impacted:** `echo_tecore.py`

---

## Section 5 — ViaPath / GTL / IRT (inmate phone, tablet, visit, deposit)

| Item | Committee answer |
|---|---|
| ViaPath platform — current ViaPath / older GTL ITS / state variant | ⚪ |
| **Integration mode** per data stream — REST / SFTP / SQL | ⚪ |
| Endpoint URLs / SFTP hosts / SQL connection strings | ⚪ |
| Auth — API key / SFTP key+passphrase / SQL creds | ⚪ |
| Field mapping per dataclass: | |
| &nbsp;&nbsp;• `InmateCall` (inmate_id, called_number, start_time, duration, ...) | ⚪ |
| &nbsp;&nbsp;• `TabletEvent` (inmate_id, event_type, contact_id, timestamp, ...) | ⚪ |
| &nbsp;&nbsp;• `VideoVisit` (inmate_id, visitor_id, scheduled_start, ...) | ⚪ |
| &nbsp;&nbsp;• `Deposit` (inmate_id, depositor_name, amount, timestamp, ...) | ⚪ |
| Watchlist source — where do "flagged contacts" live? | ⚪ |
| Poll interval / file-drop schedule / query window | ⚪ |
| Sample event for each of the four types (sanitized) | ⚪ |

**Module impacted:** `echo_viapath.py`

---

## Section 6 — Computer vision (YOLO drone, phone, violence)

| Item | Committee answer |
|---|---|
| Drone-detection model — committee weights OR public model (Roboflow) starting point OK? | ⚪ |
| Phone-detection model — same | ⚪ |
| Violence-detection model — committee weights OR open-source pretrained + local fine-tune? | ⚪ |
| Per-detector confidence thresholds (defaults: drone 0.55, phone 0.50, violence 0.65) | ⚪ |
| Frame rate per detector per camera (default 2 fps each) | ⚪ |
| Should vision frames also feed `echo_face.py`, or separate pipelines? | ⚪ |

**Module impacted:** `echo_vision.py`

---

## Section 7 — Inmate data & scheduling

| Item | Committee answer |
|---|---|
| Inmate ID format (state DOC # / FBI # / agency-internal?) | ⚪ |
| Classification taxonomy (GP / GP-low / AdSeg / Death Row / Protective / ...) | ⚪ |
| Inmate-to-housing-assignment data source (JMS / OMS / SQL replica?) | ⚪ |
| Inmate scheduling system (work detail / court / medical / visitation) — feeds `_inmate_has_scheduled_authorization()` | ⚪ |
| Sample inmate record (sanitized) | ⚪ |

**Module impacted:** `echo_zones.py`

---

## Section 8 — Zones, sites, alerts

| Item | Committee answer |
|---|---|
| Site identification (facility name, agency ID, timezone, lat/lng) | ⚪ |
| Real zone definitions to replace the sample in `echo_cameras.yaml` (Yards, Perimeter, Housing, Visitation, Programs, Industries, etc.) | ⚪ |
| Real camera-to-zone mapping | ⚪ |
| Per-zone permitted_hours rules | ⚪ |
| Per-zone permitted_classifications rules | ⚪ |
| Alert routing — actual SIU pager URL / control-center display IPC / warden email / FBI liaison contact | ⚪ |

**Modules impacted:** `echo_cameras.yaml`, `echo_alerts.py`

---

## Section 9 — Legal & policy attestations

| Item | Committee answer |
|---|---|
| Written policy authorizing biometric ID of inmates (cite policy #) | ⚪ |
| Authorization for intake-photo DB to be used for FR | ⚪ |
| Staff/visitor face-redaction policy | ⚪ |
| Tecore MAS FCC-authority filing on record | ⚪ |
| CJIS Security Policy compliance level required (1.0 / 2.0 / 5.0?) | ⚪ |
| State-specific compliance frameworks | ⚪ |
| Records retention for correlation events (default: 4-hour rolling in-memory log; long-term storage requires separate evidence pipeline) | ⚪ |
| Audit-log destination (SIEM / Splunk / Sentinel / file?) | ⚪ |
| Discovery / FOIA / public-records retention schedule | ⚪ |

**Modules impacted:** `echo_face.py`, `echo_alerts.py`, `echo_correlation.py`, `ARCHITECTURE.md`

---

## Section 10 — Test / dev environment

| Item | Committee answer |
|---|---|
| Dev or test segment of facility network available? | ⚪ |
| Synthetic / sanitized data feed available for development? | ⚪ |
| Test camera (one) — RTSP URL to validate audio pipeline | ⚪ |
| Test inmate dataset for FR validation | ⚪ |

---

## What's already runnable without ANY committee input

If the committee wants a **demo deployment** with just RTSP cameras
and no other integrations yet, that's a one-day install — just answer
Sections 1, 2, and 8 and we deploy the audio-only foundation:

- ✅ Multi-camera acoustic drone detection
- ✅ Zone rules engine (waiting for face events; emits inmate_out_of_bounds when wired)
- ✅ Correlation engine (runs on whatever events arrive; will start surfacing patterns the moment FR/MAS/ViaPath are wired)
- ✅ Alert dispatcher (email / SMS / ntfy ready; custom channels pluggable)

Everything else lights up incrementally as Sections 3-7 get filled in.

---

## Suggested fill-in order (highest value per effort)

1. **Section 2 + 8 + 1** — deploy the audio-only foundation. Day one ROI.
2. **Section 3** — committee FR. Adds zone-violation alerts and the
   strongest correlation signal (inmate identity tied to camera observations).
3. **Section 4** — Tecore MAS. Adds the single strongest external-contact
   signal (MSISDN-MAS-match, weight 0.20).
4. **Section 5** — ViaPath. Adds the rich link analysis (calls, visits,
   deposits). This is where correlation reports go from interesting to
   case-building.
5. **Section 6** — YOLO. Vision confirms audio detections and adds
   phone-in-hand events.
6. **Section 7** — inmate scheduling. Reduces false-positive
   out-of-bounds alerts.
7. **Section 9** — legal/policy. Required before going live in production;
   can run in dev/test in parallel.

Sections 1-8 are the build; Section 9 is the gate before production
cutover.
