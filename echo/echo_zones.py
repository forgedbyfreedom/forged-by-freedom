"""
ECHO Zone & Inmate-Permission Engine.

Real implementation (no ML required) — this module answers two questions
the dashboard and alert engine ask thousands of times per second:

  1. "Is inmate X allowed to be in zone Z right now?"
     - Considers permitted_hours, permitted_classifications, scheduled
       movements (work detail, court, medical, visitation), AdSeg status.
  2. "Is any inmate currently in a zone they shouldn't be?"
     - Cross-references current facial-detection events from
       echo_face.py against zone rules and emits alerts.

This file does NOT do the face recognition itself (that's echo_face.py).
It takes a stream of "inmate X seen at camera Y at time T" events and
applies the rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional

import yaml


# ── Data structures ─────────────────────────────────────────────────
@dataclass
class Zone:
    id: str
    name: str
    type: str                                       # outdoor_yard, perimeter, housing, visitation, etc.
    permitted_hours_raw: str                        # "08:00-11:00,13:00-16:30" or "always" or ""
    permitted_classifications: list[str]            # ["GP", "GP-low", ...]
    covered_by: list[str]                           # camera IDs

    def permitted_now(self, now: Optional[datetime] = None) -> bool:
        """Is this zone open for movement right now?"""
        now = now or datetime.now()
        raw = (self.permitted_hours_raw or "").strip().lower()
        if raw == "always":
            return True
        if not raw:
            return False
        current = now.time()
        for window in raw.split(","):
            window = window.strip()
            if "-" not in window:
                continue
            start_s, end_s = window.split("-", 1)
            try:
                start = _parse_hhmm(start_s)
                end = _parse_hhmm(end_s)
                if start <= current <= end:
                    return True
            except ValueError:
                continue
        return False

    def permits_classification(self, classification: str) -> bool:
        return classification in self.permitted_classifications


@dataclass
class InmateLocation:
    """One observation of an inmate seen on a camera."""
    inmate_id: str
    inmate_classification: str
    camera_id: str
    zone_ids: list[str]                             # all zones this camera covers
    timestamp: float                                # unix epoch
    face_confidence: float                          # 0.0..1.0 from echo_face.py


@dataclass
class ZoneViolation:
    inmate_id: str
    inmate_classification: str
    zone_id: str
    zone_name: str
    camera_id: str
    reason: str                                     # "out-of-hours" | "not-permitted-classification" | "double-violation"
    timestamp: float


# ── Engine ──────────────────────────────────────────────────────────
class ZoneEngine:
    """Loads zones from YAML, evaluates incoming InmateLocation events."""

    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.zones: dict[str, Zone] = {}
        # Optional plug-in: dict[inmate_id, list[ScheduledMovement]]
        # for "this inmate is on work detail in zone X 09:00-12:00 today"
        # PLACEHOLDER — see ARCHITECTURE.md § Inmate scheduling integration
        self.scheduled_movements: dict = {}
        self.reload()

    def reload(self) -> None:
        with open(self.yaml_path) as f:
            data = yaml.safe_load(f) or {}
        self.zones = {}
        for z in data.get("zones", []):
            self.zones[z["id"]] = Zone(
                id=z["id"],
                name=z["name"],
                type=z.get("type", "unknown"),
                permitted_hours_raw=z.get("permitted_hours", ""),
                permitted_classifications=z.get("permitted_classifications", []),
                covered_by=z.get("covered_by", []),
            )

    def evaluate(self, obs: InmateLocation) -> list[ZoneViolation]:
        """Return zero or more violations for a single inmate observation."""
        violations: list[ZoneViolation] = []
        for zone_id in obs.zone_ids:
            zone = self.zones.get(zone_id)
            if zone is None:
                continue

            # Check scheduled-movement override first
            if _inmate_has_scheduled_authorization(
                    self.scheduled_movements, obs.inmate_id, zone_id, obs.timestamp):
                continue

            permitted_class = zone.permits_classification(obs.inmate_classification)
            permitted_time = zone.permitted_now(datetime.fromtimestamp(obs.timestamp))

            if not permitted_class and not permitted_time:
                reason = "double-violation"
            elif not permitted_class:
                reason = "not-permitted-classification"
            elif not permitted_time:
                reason = "out-of-hours"
            else:
                continue

            violations.append(ZoneViolation(
                inmate_id=obs.inmate_id,
                inmate_classification=obs.inmate_classification,
                zone_id=zone_id,
                zone_name=zone.name,
                camera_id=obs.camera_id,
                reason=reason,
                timestamp=obs.timestamp,
            ))
        return violations


# ── helpers ─────────────────────────────────────────────────────────
def _parse_hhmm(s: str) -> time:
    s = s.strip()
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(s)
    return time(int(parts[0]), int(parts[1]))


def _inmate_has_scheduled_authorization(scheduled: dict,
                                        inmate_id: str,
                                        zone_id: str,
                                        timestamp: float) -> bool:
    """PLACEHOLDER — when the inmate scheduling integration is wired in
    (ARCHITECTURE.md § Inmate scheduling), this function will check
    whether the inmate is on a scheduled movement (work detail, court
    transport, medical appt, visitation) that authorizes their presence
    in this zone at this time. Until then, returns False (no override)."""
    return False
