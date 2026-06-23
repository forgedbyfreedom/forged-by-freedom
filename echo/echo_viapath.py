"""
ECHO ViaPath integration — inmate phone, tablet, IRT, visitation.

────────────────────────────────────────────────────────────────────────
PLACEHOLDER MODULE — see ARCHITECTURE.md § ViaPath integration
                     AND § Vendor procurement & data-sharing agreements
────────────────────────────────────────────────────────────────────────

ViaPath Technologies (formerly Global Tel*Link / GTL, rebranded 2022)
is the largest inmate-communications vendor in US corrections. They
operate:

  • Inmate phone calls (recorded + monitored, court-admissible)
  • Inmate tablets (messaging, music, ebooks, paid content)
  • IRT (Investigative Resource Tool) — the SIU/investigator-facing
    data platform that surfaces call patterns, three-way detection,
    voice biometrics, keyword alerts, etc.
  • Video visitation (replaces in-person visitation at many facilities)
  • Inmate trust-fund account deposits via ConnectNetwork

Single vendor, single API contract, multiple data streams. This module
is the integration point for ALL of them — when ViaPath data is
authorized at your facility, populate the appropriate fetch methods.

Data flows when implemented:
  ViaPath cloud  ──HTTPS/SFTP──>  echo_viapath.py  ──events──>  echo_correlation.py

Each event type below is fed into the correlation engine and time-
correlated against drone detections, MAS captures, video events, etc.

────────────────────────────────────────────────────────────────────────
PROCUREMENT & DATA-SHARING (required before any of this runs)
────────────────────────────────────────────────────────────────────────
ViaPath does NOT expose a public API. Access requires:
  • Active contract between the agency and ViaPath
  • Signed data-sharing addendum specifying which feeds + retention
  • Designated "ViaPath admin" at the facility with API credentials
  • Sometimes a Letter of Authority from the warden / state DOC
  • For voice biometric / advanced features: separate purchase tier
The integration paths are typically:
  • REST API (newer deployments, JSON over HTTPS)
  • SFTP daily/hourly CSV drops (legacy — many state DOCs still use this)
  • Direct SQL access to a read-replica (largest facilities only)
Implementation in this file should support all three.
────────────────────────────────────────────────────────────────────────

TO COMPLETE — committee / ViaPath admin must provide (see INTEGRATION_CHECKLIST.md):
  1. Integration mode: "rest" | "sftp" | "sql"
  2. Endpoint URL / SFTP host+path / SQL connection string
  3. Authentication — API key / SFTP key + passphrase / SQL credentials
  4. Field mapping — your ViaPath schema's field names → the dataclasses below
       • InmateCall: needs inmate_id, called_number, start_time, duration, ...
       • TabletEvent: needs inmate_id, event_type, contact_id, timestamp, ...
       • VideoVisit:  needs inmate_id, visitor_id, scheduled_start, ...
       • Deposit:     needs inmate_id, depositor_name, amount, timestamp, ...
  5. Watchlist source — where do "flagged contact" / "watchlist visitor"
     lists live? (Some DOCs maintain in IRT; others in a separate SIU DB.)
  6. Poll interval (REST) / file-drop schedule (SFTP) / query window (SQL)

Once provided, the only methods that need real implementation are
ViaPathConnector.start() and the four fetch_recent_*() methods.
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional


# ── Event types from ViaPath data streams ──────────────────────────
@dataclass
class InmateCall:
    inmate_id: str
    called_number: str               # often E.164 or 10-digit US
    called_party_name: Optional[str] # if PAN (Personal Allowed Numbers) match
    start_time: datetime
    duration_sec: int
    call_id: str                     # ViaPath internal reference
    flagged_keywords: list[str]      # from automated transcript scan
    three_way_suspected: bool        # IRT three-way detection
    voice_biometric_match: Optional[str]  # second-party voice ID if known

@dataclass
class TabletEvent:
    inmate_id: str
    event_type: str                  # "message_sent" | "message_recv" | "content_purchased" | "deposit_recv"
    contact_id: Optional[str]        # email/phone/contact name on the other end
    timestamp: datetime
    payload_snippet: Optional[str]   # first ~200 chars if messaging
    flagged: bool                    # any IRT flag (keyword / contact / pattern)

@dataclass
class VideoVisit:
    inmate_id: str
    visitor_id: str
    visitor_name: str
    scheduled_start: datetime
    actual_start: Optional[datetime]
    actual_duration_sec: Optional[int]
    flagged: bool
    flag_reasons: list[str]          # ["visitor_on_watch_list", "audio_keyword", etc.]

@dataclass
class Deposit:
    inmate_id: str
    depositor_name: str
    depositor_phone: Optional[str]
    depositor_email: Optional[str]
    depositor_id_hash: Optional[str] # hashed government ID if collected
    amount_usd: float
    timestamp: datetime
    funding_source: str              # "credit_card" | "western_union" | "money_order" | etc.


# ── Integration worker ─────────────────────────────────────────────
class ViaPathConnector:
    """PLACEHOLDER — polls ViaPath data streams and emits structured events.

    When implemented, this class supports three integration modes
    (configured via __init__):
      • mode="rest"  — poll ViaPath REST API every N seconds
      • mode="sftp"  — pick up nightly CSV drops from a SFTP server
      • mode="sql"   — query a read-replica SQL Server directly
    """

    def __init__(self,
                 mode: str,
                 credentials: dict,
                 on_call: Callable[[InmateCall], None],
                 on_tablet: Callable[[TabletEvent], None],
                 on_visit: Callable[[VideoVisit], None],
                 on_deposit: Callable[[Deposit], None],
                 poll_interval_sec: int = 60):
        if mode not in ("rest", "sftp", "sql"):
            raise ValueError(f"unknown mode: {mode}")
        self.mode = mode
        self.credentials = credentials   # PLACEHOLDER — load from secrets manager, NEVER inline
        self.on_call = on_call
        self.on_tablet = on_tablet
        self.on_visit = on_visit
        self.on_deposit = on_deposit
        self.poll_interval_sec = poll_interval_sec

    def start(self) -> None:
        """PLACEHOLDER — start the background polling thread."""
        pass

    def stop(self) -> None:
        """PLACEHOLDER — stop the background polling thread."""
        pass

    # ── per-stream fetch methods (placeholders) ──────────────────
    def fetch_recent_calls(self, since: datetime) -> list[InmateCall]:
        """PLACEHOLDER — IRT call records since `since`."""
        return []

    def fetch_recent_tablet_events(self, since: datetime) -> list[TabletEvent]:
        """PLACEHOLDER — tablet messaging + activity since `since`."""
        return []

    def fetch_recent_visits(self, since: datetime) -> list[VideoVisit]:
        """PLACEHOLDER — video visitation records since `since`."""
        return []

    def fetch_recent_deposits(self, since: datetime) -> list[Deposit]:
        """PLACEHOLDER — ConnectNetwork trust-fund deposits since `since`."""
        return []

    # ── visitor pre-registration lookup ──────────────────────────
    def lookup_visitor(self, visitor_id: str) -> Optional[dict]:
        """PLACEHOLDER — return the visitor's registration data.

        On modern ViaPath visitation deployments, visitors register
        before their first visit and upload:
          • Government ID (photo)
          • Phone number
          • Email
          • Relationship to inmate
          • Photo for biometric verification at visit
        This data is the spine of the link-analysis engine — it ties
        contraband-cellphone numbers and deposit-funding sources to
        specific identified visitors. See echo_correlation.py.
        """
        return None
