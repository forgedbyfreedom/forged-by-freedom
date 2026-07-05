"""
ECHO Dedrone integration — multi-sensor drone tracking confirmation.

────────────────────────────────────────────────────────────────────────
PLACEHOLDER MODULE — see INTEGRATION_CHECKLIST.md § Dedrone

Dedrone Inc. is a leading multi-sensor counter-UAS platform. A Dedrone
deployment combines RF detection (RfPatrol / Dedrone Sensors), video
(PTZ + computer vision), radar, and acoustic sensors into a single
fusion pipeline that produces a confirmed track per drone with:
  • Drone classification (manufacturer + model — e.g. DJI Mavic 3,
    Autel EVO, custom-built)
  • Real-time position (lat/lng/altitude)
  • Pilot/controller location (when RF triangulation possible)
  • Flight track history
  • Captured imagery from PTZ vision

ECHO's acoustic + visual detection sits ALONGSIDE Dedrone — different
sensor modalities catch different drones (acoustic catches small quads
Dedrone may not RF-fingerprint; Dedrone catches RF-quiet gliders ECHO
misses). Fusing both confirms more and cuts false positives.

When a Dedrone track and an ECHO detection are within 30 seconds and
within a configurable geographic radius, the correlation engine treats
it as a CONFIRMED drone event (highest confidence tier).

────────────────────────────────────────────────────────────────────────
TO COMPLETE — committee / Dedrone admin must provide:
  1. Integration mode: "rest" | "websocket" | "syslog"
  2. Dedrone DroneTracker version (5.x vs 6.x have different APIs)
  3. Endpoint URL + auth (API key / mTLS / OAuth2)
  4. Sample drone-track event (sanitized JSON)
  5. Geographic origin (the lat/lng Dedrone tracks are relative to,
     so we can do distance math to ECHO camera locations)
  6. Pilot/controller location enabled? Dedrone Pro tier feature.
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


@dataclass
class DedroneDetection:
    """One confirmed drone track from Dedrone's fusion pipeline."""
    timestamp: datetime
    track_id: str                    # persistent ID for the same drone across pings
    drone_classification: str        # "DJI Mavic 3" | "Autel EVO" | "unknown-custom" etc.
    drone_make: Optional[str]        # "DJI" | "Autel" | "Parrot" | "Skydio" | ...
    drone_model: Optional[str]       # "Mavic 3" | "EVO Lite+" | ...
    drone_serial: Optional[str]      # ⭐ STRONGEST IDENTIFIER — DJI Remote ID broadcasts
                                     # serial; matches a registered owner via FAA DroneZone
                                     # OR matches a previously-recovered drone in your
                                     # evidence locker. When present, gets max correlation
                                     # weight (see echo_correlation.signal: drone_serial_match)
    confidence: float                # 0..1 from Dedrone
    position_lat: float
    position_lng: float
    position_alt_m: float
    pilot_lat: Optional[float]       # if RF triangulation could find pilot
    pilot_lng: Optional[float]
    rf_fingerprint: Optional[str]    # device-specific RF ID (Pro tier)
    sensors_contributing: list[str]  # ["rf", "video", "radar", "acoustic"]
    raw_payload: dict = field(default_factory=dict)


class DedroneConnector:
    """PLACEHOLDER — pulls Dedrone tracks, emits DedroneDetection events."""

    def __init__(self,
                 mode: str,
                 credentials: dict,
                 on_detection: Callable[[DedroneDetection], None],
                 poll_interval_sec: int = 5):
        if mode not in ("rest", "websocket", "syslog"):
            raise ValueError(f"unknown mode: {mode}")
        self.mode = mode
        self.credentials = credentials  # PLACEHOLDER — secrets manager, NEVER inline
        self.on_detection = on_detection
        self.poll_interval_sec = poll_interval_sec

    def start(self) -> None:
        """PLACEHOLDER — REST polling loop OR websocket subscriber OR syslog listener."""
        pass

    def stop(self) -> None:
        pass

    def fetch_recent_tracks(self, since: datetime) -> list[DedroneDetection]:
        """PLACEHOLDER — Dedrone confirmed-track records since `since`."""
        return []
