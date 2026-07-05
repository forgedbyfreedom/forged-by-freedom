"""
ECHO Flock Safety integration — LPR (license plate reader) network.

────────────────────────────────────────────────────────────────────────
PLACEHOLDER MODULE — see INTEGRATION_CHECKLIST.md § Flock

Flock Safety operates a nationwide LPR camera network deployed by city
PDs, sheriffs, HOAs, and state agencies (incl. SC DPS). Cameras capture
plate, vehicle make/model/color, and a still image for every vehicle
passing within ~50 ft. Data is queryable through the Flock OS API by
authorized agencies.

For correctional drone-drop investigation, Flock is the bridge between
"a drone flew" and "this physical vehicle was outside the perimeter
loitering." Drones get launched from vehicles, then the operator drives
off. Capturing every plate that passes within 1-2 mi of the facility
in the ±30-min window around the drone is a strong investigative lead.

Combined with SC DMV lookup (echo_dmv_sc.py), every plate becomes an
identified owner + address, which can then be cross-referenced with the
ViaPath visitor registration, deposit history, and call log.

────────────────────────────────────────────────────────────────────────
TO COMPLETE — committee / Flock liaison must provide:
  1. Flock OS API endpoint (typically https://<agency>.flockos.com/api/...)
  2. API key with the right scopes (read:detections, read:vehicles)
  3. Camera IDs within 1-2 mi of the facility (Flock won't return data
     for cameras you're not authorized for, so this is a discovery step)
  4. Whether your agency has a "Network Sharing" agreement that lets
     you query OTHER agencies' Flock cameras in your state (huge for
     tracking a vehicle that drove in from out of jurisdiction)
  5. Plate hotlist integration — does Flock automatically check plates
     against NCIC / state stolen-vehicle / sex-offender registry?
     Those hits are very high-signal correlation events.
  6. Sample detection record (sanitized JSON)
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


@dataclass
class FlockDetection:
    """One vehicle pass captured by a Flock camera."""
    timestamp: datetime
    detection_id: str
    camera_id: str                   # Flock's camera identifier
    camera_name: str                 # human-readable (e.g. "Hwy 17 + 3rd")
    camera_lat: float
    camera_lng: float
    plate: str                       # OCR'd plate (may have ? for unclear chars)
    plate_state: Optional[str]       # "SC" | "NC" | "GA" | ...
    plate_confidence: float          # 0..1 OCR confidence
    vehicle_make: Optional[str]
    vehicle_model: Optional[str]
    vehicle_color: Optional[str]
    vehicle_type: Optional[str]      # "sedan" | "suv" | "pickup" | etc.
    direction_of_travel: Optional[str]  # "northbound" | "southbound" | ...
    hotlist_hit: bool                # NCIC / state hotlist match
    hotlist_categories: list[str]    # ["stolen", "wanted", "sex_offender", ...]
    image_url: Optional[str]         # link to the still image
    raw_payload: dict = field(default_factory=dict)


class FlockConnector:
    """PLACEHOLDER — pulls Flock detections, emits FlockDetection events."""

    def __init__(self,
                 api_endpoint: str,
                 api_key: str,
                 authorized_camera_ids: list[str],
                 on_detection: Callable[[FlockDetection], None],
                 poll_interval_sec: int = 30):
        self.api_endpoint = api_endpoint   # PLACEHOLDER — committee provides
        self.api_key = api_key             # PLACEHOLDER — secrets manager
        self.authorized_camera_ids = authorized_camera_ids
        self.on_detection = on_detection
        self.poll_interval_sec = poll_interval_sec

    def start(self) -> None:
        """PLACEHOLDER — poll Flock OS API every N seconds, fire events."""
        pass

    def stop(self) -> None:
        pass

    def fetch_recent_detections(self,
                                since: datetime,
                                limit: int = 1000) -> list[FlockDetection]:
        """PLACEHOLDER — fetch detections since `since` for authorized cameras."""
        return []

    def search_plate_history(self,
                             plate: str,
                             since: datetime,
                             until: Optional[datetime] = None) -> list[FlockDetection]:
        """PLACEHOLDER — historical lookup for a specific plate.
        Used by the correlation engine when a suspect plate emerges."""
        return []
