"""
ECHO Tecore MAS integration — contraband cellphone capture events.

────────────────────────────────────────────────────────────────────────
PLACEHOLDER MODULE — see ARCHITECTURE.md § Tecore MAS integration
                     AND § Vendor procurement & data-sharing agreements
────────────────────────────────────────────────────────────────────────

Tecore Networks (tecore.com) makes the leading Managed Access System
(MAS) deployed in US correctional facilities. A MAS is a private LTE/
5G basestation deployed inside the facility's RF footprint that:

  • Allows authorized devices (staff phones, approved tablets) to
    register and connect to the carrier network normally
  • Captures every unauthorized cellphone that powers on inside the
    facility — IMSI, IMEI, attempted destinations, time of attempt
  • Blocks the unauthorized device from completing calls / SMS / data
    (the device sees "no service" or a service-denial code)
  • Logs every capture event for SIU review

Tecore's product is sometimes branded iNAC ("Intelligent Network
Access Controller") + specific MAS deployments. Output is a structured
event feed.

This module is the integration point. When MAS data is authorized at
your facility, populate the polling / push handler with the vendor's
specific API or CSV-drop format.

Data flow when implemented:
  Tecore MAS  ──HTTPS/SFTP/syslog──>  echo_tecore.py  ──events──>  echo_correlation.py

A MAS capture event is one of the strongest signals available — it
proves a contraband phone existed in the facility at a specific time
in a specific RF cell (which maps to housing block / yard / etc.).
Correlated with drone-detection events and inmate-location events,
this is what builds an indictment.

────────────────────────────────────────────────────────────────────────
PROCUREMENT & DATA-SHARING (required before any of this runs)
────────────────────────────────────────────────────────────────────────
Tecore data feeds typically require:
  • Active Tecore MAS deployment at the facility
  • Signed data-sharing addendum specifying which fields the agency
    can extract (some carriers restrict what Tecore can share)
  • Coordination with the agency's FCC-licensed RF coordinator (MAS
    operates under FCC Part 27 / 90 special-temporary-authority)
  • Sometimes a state-level approval — MAS interferes with the
    carrier network and many states require formal coordination
The integration paths are typically:
  • REST API (newer MAS deployments)
  • Syslog over TLS (real-time event stream)
  • SFTP daily CSV drops (legacy)
Implementation should support all three.
────────────────────────────────────────────────────────────────────────

TO COMPLETE — committee / Tecore admin must provide (see INTEGRATION_CHECKLIST.md):
  1. Integration mode: "rest" | "syslog" | "sftp"
  2. Endpoint URL / syslog listen-port / SFTP host+path
  3. Authentication — API key / mTLS cert / SFTP key
  4. Field mapping — your Tecore schema's field names → MasCaptureEvent
       • Need: timestamp, imei, imsi, msisdn (if resolved), rf_cell_id,
         attempted_action, destination, blocked, signal_strength_dbm,
         first_seen_at_facility
  5. RF cell → housing block mapping (echo_correlation needs to know
     which housing block each MAS rf_cell_id covers, so it can match
     MAS captures to inmate housing assignments). Usually a small static
     dict provided by the agency RF coordinator.
  6. Poll interval (REST) / syslog facility code / file-drop schedule (SFTP)

Once provided, the only methods that need real implementation are
TecoreConnector.start() and fetch_recent_captures().
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


# ── Event types from MAS captures ──────────────────────────────────
@dataclass
class MasCaptureEvent:
    """One unauthorized cellphone capture by the MAS."""
    timestamp: datetime
    imei: str                        # device hardware ID
    imsi: str                        # SIM card ID
    msisdn: Optional[str]            # if the MAS could resolve it (phone number)
    carrier: Optional[str]           # T-Mobile / Verizon / AT&T / etc.
    rf_cell_id: str                  # which MAS cell captured (housing block / yard / etc.)
    attempted_action: str            # "voice_call" | "sms" | "data" | "registration"
    destination: Optional[str]       # destination number / APN attempted
    blocked: bool                    # whether the MAS blocked the attempt
    signal_strength_dbm: float       # for triangulation if multiple cells
    first_seen_at_facility: Optional[datetime]  # earliest record of this IMEI/IMSI

    @property
    def is_new_device(self) -> bool:
        """True if this is the first time this IMEI has been seen here."""
        return (self.first_seen_at_facility is None
                or self.first_seen_at_facility == self.timestamp)


@dataclass
class MasDeviceProfile:
    """Aggregated profile of a captured device built up over many events."""
    imei: str
    imsi: str
    msisdn: Optional[str]
    carrier: Optional[str]
    first_seen: datetime
    last_seen: datetime
    total_captures: int
    rf_cells_observed: set = field(default_factory=set)
    destinations_attempted: set = field(default_factory=set)
    is_active: bool = True


# ── Integration worker ─────────────────────────────────────────────
class TecoreConnector:
    """PLACEHOLDER — connects to a Tecore MAS data feed and emits events.

    When implemented, this class supports three integration modes:
      • mode="rest"   — poll the MAS REST API every N seconds
      • mode="syslog" — listen for real-time syslog-over-TLS pushes
      • mode="sftp"   — pick up daily CSV drops from an SFTP server
    """

    def __init__(self,
                 mode: str,
                 credentials: dict,
                 on_capture: Callable[[MasCaptureEvent], None],
                 poll_interval_sec: int = 30):
        if mode not in ("rest", "syslog", "sftp"):
            raise ValueError(f"unknown mode: {mode}")
        self.mode = mode
        self.credentials = credentials   # PLACEHOLDER — secrets manager, NEVER inline
        self.on_capture = on_capture
        self.poll_interval_sec = poll_interval_sec

    def start(self) -> None:
        """PLACEHOLDER — start the polling / listening thread."""
        pass

    def stop(self) -> None:
        """PLACEHOLDER — stop the polling / listening thread."""
        pass

    def fetch_recent_captures(self, since: datetime) -> list[MasCaptureEvent]:
        """PLACEHOLDER — MAS capture events since `since`."""
        return []

    def get_device_profile(self, imei: str) -> Optional[MasDeviceProfile]:
        """PLACEHOLDER — historical profile for a specific IMEI."""
        return None
