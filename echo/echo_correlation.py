"""
ECHO Link-Analysis & Correlation Engine.

REAL implementation — this is the heart of "tie an inmate or civilian
to the drone."  It ingests events from every other subsystem and
surfaces correlations that build a case package for SIU.

The engine keeps a rolling time-windowed event log (default ±15 min
around every drone detection, configurable up to 4 hours) in memory.
When a drone is detected, it runs a correlation pass that scores every
known inmate and every known external contact on multiple weak signals,
and ranks the top candidates.

Signals (each scored 0..1, then weighted; weights configurable):

  Inmate-side signals (who in the facility caused / received the drop)
    • inmate_outdoors_at_drone_time     — face seen on outdoor camera ±5 min
    • inmate_on_phone_at_drone_time     — voice call active ±5 min
    • inmate_phone_in_hand_visual       — phone-in-hand visual ±5 min
    • inmate_mas_capture_correlation    — MAS captured a phone in their
                                          housing block ±5 min
    • inmate_recent_visitor_contact     — visit/call/tablet contact with
                                          a known drone operator in the
                                          past 30 days
    • inmate_recent_deposit_anomaly     — large deposit from new source
                                          in the past 14 days
    • inmate_history                    — prior drone-related incidents

  External-contact-side signals (who outside orchestrated the drop)
    • contact_called_inmate_pre_drop    — call to inmate ±60 min before drop
    • contact_visited_recently          — in-person/video visit in past 14d
    • contact_deposited_recently        — deposit in past 14d
    • contact_known_associate           — known to another inmate with prior drone activity

The engine emits a CorrelationReport per drone detection that lists
the top N candidates with their score breakdown and the evidence trail.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional


# ── Canonical clock ─────────────────────────────────────────────────
# All internal timestamps are tz-aware UTC. Naive datetimes coming in
# from callers get normalized on ingest. Mixing naive + aware raises
# TypeError in comparisons, so this is enforced not optional.
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(ts: datetime) -> datetime:
    """Coerce any datetime to tz-aware UTC.

    - Naive input is assumed to be local wall clock, converted to UTC.
    - Aware input is converted to UTC.
    """
    if ts.tzinfo is None:
        return ts.astimezone(timezone.utc) if hasattr(ts, "astimezone") else ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


# ── Generic event envelope used by every subsystem ─────────────────
@dataclass
class Event:
    """A single observation from any data source."""
    source: str                       # "drone_audio" | "drone_visual" | "face" | "viapath_call" | "viapath_tablet" | "viapath_visit" | "viapath_deposit" | "mas_capture" | "vision_phone" | "vision_violence" | "zone_violation"
    timestamp: datetime
    payload: dict                     # source-specific fields


@dataclass
class CorrelationCandidate:
    """One ranked candidate from a correlation pass."""
    subject_type: str                 # "inmate" | "external_contact"
    subject_id: str
    subject_name: Optional[str]
    score: float                      # 0..1
    signal_scores: dict               # {"inmate_outdoors_at_drone_time": 0.9, ...}
    evidence: list[dict]              # the events that contributed


@dataclass
class CorrelationReport:
    drone_event_id: str
    drone_timestamp: datetime
    drone_camera: str
    drone_confidence: float
    inmate_candidates: list[CorrelationCandidate]
    external_candidates: list[CorrelationCandidate]
    generated_at: datetime
    # Drone-centric corroborating signals (Dedrone confirmation, serial, etc.)
    drone_signals: dict = field(default_factory=dict)
    drone_signal_evidence: list[dict] = field(default_factory=list)
    # ── Fault-tolerance / health metadata ────────────────────
    subsystem_health: dict = field(default_factory=dict)   # {name: "OK"|"DEGRADED"|"DOWN"|"UNKNOWN"}
    contributing_subsystems: list[str] = field(default_factory=list)
    dropped_subsystems: list[str] = field(default_factory=list)  # DOWN/UNKNOWN, contributions ignored
    decision_declined: bool = False
    decision_declined_reason: Optional[str] = None


# ── Signal weights (tuned over time as data accumulates) ───────────
DEFAULT_WEIGHTS = {
    # ── Inmate signals ────────────────────────────────────────
    "inmate_outdoors_at_drone_time":      0.14,
    "inmate_on_phone_at_drone_time":      0.12,
    "inmate_phone_in_hand_visual":        0.14,
    "inmate_mas_capture_correlation":     0.14,
    "inmate_recent_visitor_contact":      0.06,
    "inmate_recent_deposit_anomaly":      0.06,
    "inmate_history":                     0.04,
    "inmate_zone_violation":              0.06,
    "inmate_pan_called_by_seized_phone":  0.16,  # Cellebrite: seized phone called this inmate's PAN
    "inmate_cellebrite_msg_thread":       0.10,  # Cellebrite messages with this inmate's known external contacts

    # ── External-contact signals ──────────────────────────────
    "contact_called_inmate_pre_drop":     0.22,
    "contact_visited_recently":           0.10,
    "contact_deposited_recently":         0.10,
    "contact_known_associate":            0.14,
    "contact_msisdn_matches_mas":         0.20,  # strongest single-source link
    "contact_plate_at_perimeter":         0.16,  # Flock: vehicle pass within 30 min of drone
    "contact_plate_hotlist":              0.10,  # Flock NCIC / state-list hit
    "contact_dmv_owner_in_viapath":       0.18,  # DMV-resolved owner appears in ViaPath records
    "contact_cellebrite_location_near":   0.20,  # Cellebrite GPS pings near drop site
    "contact_cellebrite_drone_app":       0.18,  # Cellebrite app data shows drone-control app

    # ── Drone-centric signals (boost drone-event confidence) ──
    "drone_dedrone_confirmed":            0.30,  # Dedrone confirmed within ±30s of acoustic
    "drone_serial_known":                 0.40,  # Dedrone got serial — STRONGEST identifier
    "drone_serial_matches_recovery":      0.50,  # serial matches a previously-recovered drone
    "drone_lora_link_detected":           0.22,  # LoRa/LoRaWAN chirp in facility RF band ±90s
                                                 # (sub-GHz control link — home-built drop rigs
                                                 #  and ExpressLRS-900 that Dedrone often misses)
    "drone_lora_bearing_toward_facility": 0.28,  # KrakenSDR direction-finding puts the LoRa
                                                 # ground station within a bearing cone that
                                                 # intersects the facility perimeter
}


# ── Source → subsystem name resolver ─────────────────────────────
# CORTEX consults the health registry per subsystem, not per raw event
# source. This map turns Event.source into the health-registry key.
SOURCE_TO_SUBSYSTEM: dict[str, str] = {
    "drone_audio":         "acoustic",
    "drone_visual":        "vision",
    "vision_phone":        "vision",
    "vision_violence":     "vision",
    "face":                "face",
    "dedrone_detection":   "dedrone",
    "flock_detection":     "flock",
    "dmv_lookup":          "dmv",
    "cellebrite_location": "cellebrite",
    "cellebrite_app_data": "cellebrite",
    "cellebrite_call":     "cellebrite",
    "cellebrite_message":  "cellebrite",
    "mas_capture":         "tecore",
    "viapath_call":        "viapath",
    "viapath_tablet":      "viapath",
    "viapath_visit":       "viapath",
    "viapath_deposit":     "viapath",
    "lora_detection":      "lora",
    "zone_violation":      "zones",
    "drone_forensics":     "drone_forensics",
}


def _subsystem_for_source(source: str) -> str:
    return SOURCE_TO_SUBSYSTEM.get(source, source)


# ── Engine ─────────────────────────────────────────────────────────
class CorrelationEngine:
    """
    Rolling-window event log + on-demand correlation passes.

    Also acts as CORTEX's fusion layer: consults the health registry so
    signals from DOWN subsystems drop out and signals from DEGRADED
    subsystems weigh half. If too few subsystems are alive at fusion
    time (< min_viable_sensors), returns a report tagged
    `decision_declined=True` instead of guessing from thin data.
    """

    def __init__(self,
                 window_hours: int = 4,
                 weights: Optional[dict] = None,
                 on_report: Optional[Callable[[CorrelationReport], None]] = None,
                 *,
                 health_registry=None,
                 min_viable_sensors: int = 2):
        self.window = timedelta(hours=window_hours)
        self.weights = weights or DEFAULT_WEIGHTS
        self.on_report = on_report
        self.min_viable_sensors = min_viable_sensors
        # Late import to avoid cycles; caller can pass a custom registry
        if health_registry is None:
            try:
                from echo_health import REGISTRY as _R
                health_registry = _R
            except Exception:
                health_registry = None
        self.health = health_registry

        # Time-indexed events, oldest auto-pruned
        self._events: deque[Event] = deque()
        # Lookup indexes for fast correlation
        self._by_source: defaultdict[str, list] = defaultdict(list)
        self._by_inmate: defaultdict[str, list] = defaultdict(list)
        self._by_msisdn: defaultdict[str, list] = defaultdict(list)
        self._lock = threading.RLock()

    # ── Health-aware weighting ───────────────────────────────
    def _weight_for_source(self, source: str) -> float:
        """1.0 (OK) / 0.5 (DEGRADED) / 0.0 (DOWN / UNKNOWN)."""
        if not self.health:
            return 1.0
        return self.health.fusion_weight(_subsystem_for_source(source))

    def _weight_for_source_name(self, subsystem: str) -> float:
        """Direct lookup by subsystem name (skips the source → subsystem map)."""
        if not self.health:
            return 1.0
        return self.health.fusion_weight(subsystem)

    # ── Ingest ────────────────────────────────────────────────
    def ingest(self, event: Event) -> None:
        # Normalize timestamp to tz-aware UTC so downstream comparisons
        # never mix naive and aware. Vendor connectors typically emit
        # tz-aware; the acoustic path emits naive.
        if event.timestamp.tzinfo is None:
            event = Event(source=event.source,
                          timestamp=_to_utc(event.timestamp),
                          payload=event.payload)
        with self._lock:
            self._events.append(event)
            self._by_source[event.source].append(event)
            inmate_id = event.payload.get("inmate_id")
            if inmate_id:
                self._by_inmate[inmate_id].append(event)
            msisdn = event.payload.get("msisdn") or event.payload.get("called_number")
            if msisdn:
                self._by_msisdn[msisdn].append(event)
            self._prune()
        # Auto-trigger correlation on drone events
        if event.source in ("drone_audio", "drone_visual"):
            report = self.correlate_drone(event)
            if self.on_report and report:
                self.on_report(report)

    def _prune(self) -> None:
        """Drop events older than window from every index."""
        cutoff = _utcnow() - self.window
        while self._events and self._events[0].timestamp < cutoff:
            old = self._events.popleft()
            # Best-effort cleanup of every index that could hold `old`
            try:
                self._by_source[old.source].remove(old)
            except ValueError:
                pass
            inmate = old.payload.get("inmate_id")
            if inmate:
                try:
                    self._by_inmate[inmate].remove(old)
                except ValueError:
                    pass
            # C1 fix: msisdn was leaking forever — every ViaPath call
            # accumulated. Mirror the inmate cleanup here.
            msisdn = old.payload.get("msisdn") or old.payload.get("called_number")
            if msisdn:
                try:
                    self._by_msisdn[msisdn].remove(old)
                except ValueError:
                    pass

    # ── Correlation pass ─────────────────────────────────────
    def correlate_drone(self,
                        drone_event: Event,
                        top_n: int = 10) -> CorrelationReport:
        """Score every candidate and return ranked report."""
        # Normalize the drone-event timestamp — the caller may have
        # constructed it directly rather than going through ingest().
        t = _to_utc(drone_event.timestamp) if drone_event.timestamp.tzinfo is None \
            else drone_event.timestamp

        # C2 fix: pre-check runs UNDER the lock so an ingest thread
        # can't mutate _by_source mid-iteration.
        with self._lock:
            # ── CORTEX fusion pre-check: subsystem health ──
            # DOWN → weight 0 (dropped from scoring); DEGRADED → 0.5; OK → 1.0.
            subsystems_in_window: set[str] = {
                _subsystem_for_source(s) for s, evs in self._by_source.items()
                if evs
            }
            health_snapshot: dict[str, str] = {}
            contributing: list[str] = []
            dropped: list[str] = []
            for sub in subsystems_in_window:
                if self.health:
                    st = self.health.status_of(sub)
                    health_snapshot[sub] = st.value
                else:
                    health_snapshot[sub] = "OK"
                w = self._weight_for_source_name(sub)
                (dropped if w == 0.0 else contributing).append(sub)

            # min-viable-sensor threshold — decline to decide instead of guessing
            if len(contributing) < self.min_viable_sensors:
                return CorrelationReport(
                    drone_event_id=str(id(drone_event)),
                    drone_timestamp=t,
                    drone_camera=drone_event.payload.get("camera_id", "unknown"),
                    drone_confidence=float(drone_event.payload.get("confidence", 0.0)),
                    inmate_candidates=[],
                    external_candidates=[],
                    generated_at=_utcnow(),
                    subsystem_health=health_snapshot,
                    contributing_subsystems=sorted(contributing),
                    dropped_subsystems=sorted(dropped),
                    decision_declined=True,
                    decision_declined_reason=(
                        f"only {len(contributing)} viable sensor(s) "
                        f"(need ≥ {self.min_viable_sensors}); dropped: {sorted(dropped)}"
                    ),
                )

            inmate_scores: dict[str, dict] = {}
            for inmate_id, inmate_events in list(self._by_inmate.items()):
                inmate_scores[inmate_id] = self._score_inmate(
                    inmate_id, inmate_events, t)

            contact_scores: dict[str, dict] = {}
            for msisdn, msisdn_events in list(self._by_msisdn.items()):
                contact_scores[msisdn] = self._score_contact(
                    msisdn, msisdn_events, t)

        inmate_candidates = [
            CorrelationCandidate(
                subject_type="inmate",
                subject_id=iid,
                subject_name=v.get("name"),
                score=v["composite"],
                signal_scores=v["signals"],
                evidence=v["evidence"],
            )
            for iid, v in inmate_scores.items()
            if v["composite"] > 0
        ]
        inmate_candidates.sort(key=lambda c: c.score, reverse=True)

        contact_candidates = [
            CorrelationCandidate(
                subject_type="external_contact",
                subject_id=msisdn,
                subject_name=v.get("name"),
                score=v["composite"],
                signal_scores=v["signals"],
                evidence=v["evidence"],
            )
            for msisdn, v in contact_scores.items()
            if v["composite"] > 0
        ]
        contact_candidates.sort(key=lambda c: c.score, reverse=True)

        # Drone-centric signals: look for Dedrone confirmation, serial,
        # serial-matches-recovery within ±30s of the drone event
        drone_signals: dict[str, float] = {}
        drone_signal_evidence: list[dict] = []
        # Fusion: skip Dedrone signals if the Dedrone subsystem is DOWN
        _dedrone_up = self._weight_for_source("dedrone_detection") > 0.0
        _lora_up    = self._weight_for_source("lora_detection") > 0.0
        for ev in (self._by_source.get("dedrone_detection", []) if _dedrone_up else []):
            if abs((ev.timestamp - t).total_seconds()) <= 30:
                drone_signals["drone_dedrone_confirmed"] = 1.0
                drone_signal_evidence.append({
                    "source": ev.source,
                    "summary": f"Dedrone confirmed track {ev.payload.get('track_id')} "
                               f"({ev.payload.get('drone_classification', 'unknown class')})",
                    "timestamp": ev.timestamp.isoformat(),
                })
                if ev.payload.get("drone_serial"):
                    drone_signals["drone_serial_known"] = 1.0
                    drone_signal_evidence.append({
                        "source": ev.source,
                        "summary": f"⭐ serial: {ev.payload['drone_serial']}",
                        "timestamp": ev.timestamp.isoformat(),
                    })
                    if ev.payload.get("serial_matches_recovery_case_id"):
                        drone_signals["drone_serial_matches_recovery"] = 1.0
                        drone_signal_evidence.append({
                            "source": "drone_forensics",
                            "summary": (f"⭐⭐ serial matches recovered drone case "
                                        f"{ev.payload['serial_matches_recovery_case_id']} — "
                                        f"same physical airframe, repeat operation"),
                            "timestamp": ev.timestamp.isoformat(),
                        })

        # LoRa/LoRaWAN sub-GHz link within ±90s of the drone event
        # (echo_lora.py — home-built drop rigs / ExpressLRS-900 that
        # Dedrone's 2.4/5.8 GHz-tuned coverage typically misses)
        for ev in (self._by_source.get("lora_detection", []) if _lora_up else []):
            if abs((ev.timestamp - t).total_seconds()) <= 90:
                drone_signals["drone_lora_link_detected"] = 1.0
                proto = ev.payload.get("protocol_guess", "lora_unknown")
                freq_mhz = ev.payload.get("center_freq_hz", 0) / 1e6
                drone_signal_evidence.append({
                    "source": ev.source,
                    "summary": (f"LoRa chirp {proto} @ {freq_mhz:.3f} MHz "
                                f"RSSI {ev.payload.get('rssi_dbm', 0):.0f} dBm "
                                f"(sub-GHz drone control link)"),
                    "timestamp": ev.timestamp.isoformat(),
                })
                bearing = ev.payload.get("source_bearing_deg")
                if bearing is not None:
                    drone_signals["drone_lora_bearing_toward_facility"] = 1.0
                    drone_signal_evidence.append({
                        "source": ev.source,
                        "summary": (f"⭐ direction-finding bearing {bearing:.1f}° "
                                    f"toward facility (KrakenSDR)"),
                        "timestamp": ev.timestamp.isoformat(),
                    })

        return CorrelationReport(
            drone_event_id=str(id(drone_event)),
            drone_timestamp=t,
            drone_camera=drone_event.payload.get("camera_id", "unknown"),
            drone_confidence=float(drone_event.payload.get("confidence", 0.0)),
            inmate_candidates=inmate_candidates[:top_n],
            external_candidates=contact_candidates[:top_n],
            generated_at=_utcnow(),
            drone_signals=drone_signals,
            drone_signal_evidence=drone_signal_evidence,
            subsystem_health=health_snapshot,
            contributing_subsystems=sorted(contributing),
            dropped_subsystems=sorted(dropped),
        )

    # ── Per-subject scoring ──────────────────────────────────
    def _score_inmate(self, inmate_id: str, events: list,
                      drone_t: datetime) -> dict:
        signals: dict[str, float] = {}
        evidence: list[dict] = []
        name = None

        for ev in events:
            # CORTEX fusion: drop events from DOWN / UNKNOWN subsystems.
            # DEGRADED still contributes at full weight here — the report
            # tags it in `subsystem_health` so operators can see which
            # contributions came from a shaky sensor.
            if self._weight_for_source(ev.source) == 0.0:
                continue
            dt = abs((ev.timestamp - drone_t).total_seconds())
            payload = ev.payload
            name = payload.get("inmate_name") or name

            if ev.source == "face" and dt <= 5 * 60:
                if payload.get("zone_type") in ("outdoor_yard", "perimeter"):
                    signals["inmate_outdoors_at_drone_time"] = max(
                        signals.get("inmate_outdoors_at_drone_time", 0),
                        _decay_score(dt, 5 * 60))
                    evidence.append({"source": ev.source,
                                     "summary": f"seen on {payload.get('camera_id')} {dt:.0f}s away",
                                     "timestamp": ev.timestamp.isoformat()})

            if ev.source == "viapath_call" and dt <= 5 * 60:
                signals["inmate_on_phone_at_drone_time"] = max(
                    signals.get("inmate_on_phone_at_drone_time", 0),
                    _decay_score(dt, 5 * 60))
                evidence.append({"source": ev.source,
                                 "summary": f"call to {payload.get('called_number')}, {dt:.0f}s away",
                                 "timestamp": ev.timestamp.isoformat()})

            if ev.source == "vision_phone" and dt <= 5 * 60:
                signals["inmate_phone_in_hand_visual"] = max(
                    signals.get("inmate_phone_in_hand_visual", 0),
                    _decay_score(dt, 5 * 60))
                evidence.append({"source": ev.source,
                                 "summary": f"phone-in-hand on {payload.get('camera_id')}",
                                 "timestamp": ev.timestamp.isoformat()})

            if ev.source == "mas_capture" and dt <= 5 * 60:
                if payload.get("rf_cell_id") == payload.get("inmate_housing_rf_cell"):
                    signals["inmate_mas_capture_correlation"] = max(
                        signals.get("inmate_mas_capture_correlation", 0),
                        _decay_score(dt, 5 * 60))
                    evidence.append({"source": ev.source,
                                     "summary": f"MAS captured IMEI {payload.get('imei')} in {payload.get('rf_cell_id')}",
                                     "timestamp": ev.timestamp.isoformat()})

            if ev.source in ("viapath_visit", "viapath_call", "viapath_tablet") \
                    and dt <= 30 * 86400 and payload.get("contact_on_watch_list"):
                signals["inmate_recent_visitor_contact"] = max(
                    signals.get("inmate_recent_visitor_contact", 0), 0.8)
                evidence.append({"source": ev.source,
                                 "summary": f"recent {ev.source} with watchlist contact",
                                 "timestamp": ev.timestamp.isoformat()})

            if ev.source == "viapath_deposit" and dt <= 14 * 86400:
                if payload.get("amount_usd", 0) >= 300 and payload.get("new_depositor"):
                    signals["inmate_recent_deposit_anomaly"] = max(
                        signals.get("inmate_recent_deposit_anomaly", 0), 0.7)
                    evidence.append({"source": ev.source,
                                     "summary": f"${payload['amount_usd']:.0f} deposit from new source",
                                     "timestamp": ev.timestamp.isoformat()})

            if ev.source == "zone_violation" and dt <= 5 * 60:
                signals["inmate_zone_violation"] = max(
                    signals.get("inmate_zone_violation", 0),
                    _decay_score(dt, 5 * 60))
                evidence.append({"source": ev.source,
                                 "summary": f"zone violation {payload.get('reason')}",
                                 "timestamp": ev.timestamp.isoformat()})

        composite = sum(signals.get(k, 0) * w for k, w in self.weights.items()
                        if k.startswith("inmate_"))
        return {"composite": composite, "signals": signals,
                "evidence": evidence, "name": name}

    def _score_contact(self, msisdn: str, events: list,
                       drone_t: datetime) -> dict:
        signals: dict[str, float] = {}
        evidence: list[dict] = []
        name = None

        for ev in events:
            # CORTEX fusion: drop events from DOWN / UNKNOWN subsystems.
            if self._weight_for_source(ev.source) == 0.0:
                continue
            dt = abs((ev.timestamp - drone_t).total_seconds())
            payload = ev.payload
            name = payload.get("called_party_name") or payload.get("visitor_name") \
                   or payload.get("depositor_name") or name

            if ev.source == "viapath_call" and dt <= 60 * 60:
                signals["contact_called_inmate_pre_drop"] = max(
                    signals.get("contact_called_inmate_pre_drop", 0),
                    _decay_score(dt, 60 * 60))
                evidence.append({"source": ev.source,
                                 "summary": f"call to inmate {payload.get('inmate_id')}, {dt:.0f}s before drone",
                                 "timestamp": ev.timestamp.isoformat()})

            if ev.source == "viapath_visit" and dt <= 14 * 86400:
                signals["contact_visited_recently"] = max(
                    signals.get("contact_visited_recently", 0), 0.7)
                evidence.append({"source": ev.source,
                                 "summary": f"visit to inmate {payload.get('inmate_id')}",
                                 "timestamp": ev.timestamp.isoformat()})

            if ev.source == "viapath_deposit" and dt <= 14 * 86400:
                signals["contact_deposited_recently"] = max(
                    signals.get("contact_deposited_recently", 0), 0.7)
                evidence.append({"source": ev.source,
                                 "summary": f"deposit ${payload.get('amount_usd', 0):.0f}",
                                 "timestamp": ev.timestamp.isoformat()})

            if ev.source == "mas_capture" and payload.get("msisdn") == msisdn:
                signals["contact_msisdn_matches_mas"] = 1.0
                evidence.append({"source": ev.source,
                                 "summary": f"MAS captured this phone number inside the facility",
                                 "timestamp": ev.timestamp.isoformat()})

            # Flock plate pass near perimeter within ±30 min of drone
            if ev.source == "flock_detection" and dt <= 30 * 60:
                if payload.get("plate") == msisdn:  # msisdn key reused for plate
                    signals["contact_plate_at_perimeter"] = max(
                        signals.get("contact_plate_at_perimeter", 0),
                        _decay_score(dt, 30 * 60))
                    evidence.append({"source": ev.source,
                                     "summary": f"plate {payload.get('plate')} on {payload.get('camera_name')}, {dt:.0f}s away",
                                     "timestamp": ev.timestamp.isoformat()})
                    if payload.get("hotlist_hit"):
                        signals["contact_plate_hotlist"] = 1.0
                        evidence.append({"source": ev.source,
                                         "summary": f"hotlist hit: {payload.get('hotlist_categories')}",
                                         "timestamp": ev.timestamp.isoformat()})

            # DMV owner of plate also appears in ViaPath records
            if ev.source == "dmv_lookup" and payload.get("owner_in_viapath_records"):
                signals["contact_dmv_owner_in_viapath"] = 1.0
                evidence.append({"source": ev.source,
                                 "summary": f"DMV owner '{payload.get('owner_name')}' has prior ViaPath contact",
                                 "timestamp": ev.timestamp.isoformat()})

            # Cellebrite — phone location near drone drop site
            if ev.source == "cellebrite_location" and dt <= 60 * 60:
                signals["contact_cellebrite_location_near"] = max(
                    signals.get("contact_cellebrite_location_near", 0),
                    _decay_score(dt, 60 * 60))
                evidence.append({"source": ev.source,
                                 "summary": f"seized phone GPS within {payload.get('accuracy_m')}m of drop site",
                                 "timestamp": ev.timestamp.isoformat()})

            # Cellebrite — drone-control app on seized phone
            if ev.source == "cellebrite_app_data" and \
                    payload.get("app_name", "").lower() in ("dji fly", "dji go 4", "autel explorer", "skydio", "litchi"):
                signals["contact_cellebrite_drone_app"] = 1.0
                evidence.append({"source": ev.source,
                                 "summary": f"seized phone had {payload.get('app_name')} installed",
                                 "timestamp": ev.timestamp.isoformat()})

        composite = sum(signals.get(k, 0) * w for k, w in self.weights.items()
                        if k.startswith("contact_"))
        return {"composite": composite, "signals": signals,
                "evidence": evidence, "name": name}


# ── Helpers ────────────────────────────────────────────────────────
def _decay_score(elapsed_sec: float, window_sec: float) -> float:
    """Linear decay from 1.0 at t=0 to 0.0 at t=window. Negative clamped."""
    if elapsed_sec <= 0:
        return 1.0
    if elapsed_sec >= window_sec:
        return 0.0
    return 1.0 - (elapsed_sec / window_sec)
