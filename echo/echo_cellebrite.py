"""
ECHO Cellebrite extraction ingestion — forensic data from seized phones.

────────────────────────────────────────────────────────────────────────
PLACEHOLDER MODULE — see INTEGRATION_CHECKLIST.md § Cellebrite

When SIU recovers a contraband cellphone (via shakedown, MAS-triggered
search, or post-drone-drop intercept), Cellebrite UFED is the dominant
forensic-extraction tool used to pull data off the device. The output
of an extraction is a UFDR (Universal Forensic Data Report) file —
a structured archive containing:

  • Call log (incoming, outgoing, missed, with timestamps + numbers)
  • SMS / MMS / iMessage / chat-app messages (WhatsApp, Signal, etc.)
  • Contacts
  • Photos + EXIF (often including GPS coords)
  • Videos
  • App data (FB Messenger, Instagram DMs, Cash App, Venmo)
  • Location history (Google Maps, Find My, app pings)
  • Browser history
  • Installed apps + login tokens

For drone-drop link analysis, the gold is:
  • Call log + messages — proves communication with inmate's known
    PAN (Personal Allowed Numbers) or with previously-identified
    external orchestrators
  • Photo EXIF GPS — proves the phone was physically at the drone
    launch site / facility perimeter at the time of the drop
  • App data — Cash App / Venmo transactions tied to inmate deposits
  • Drone control apps (DJI Fly, Autel Explorer) — proves the phone
    was used to control a drone, with flight logs sometimes recoverable

Cellebrite extractions are NOT cloud — they're produced by an
operator on a Cellebrite Touch or UFED 4PC station, locally. The
output UFDR file lands in a forensic file share. ECHO ingests by
watching that share for new UFDRs and parsing them into events.

────────────────────────────────────────────────────────────────────────
TO COMPLETE — committee / SIU lab must provide:
  1. UFDR drop directory (network share path or SFTP host)
  2. Authentication for that share (Kerberos / SMB creds / SSH key)
  3. Chain-of-custody metadata expected on each UFDR (case ID,
     extracting officer, source device IMEI/IMSI, etc.)
  4. UFDR parser library — Cellebrite ships a Reader SDK; alternatives:
     ufed2json, ALEAPP, plaso. Committee picks one.
  5. PII redaction policy — what does the correlation engine STORE
     vs. just reference by hash? (Cellebrite extractions can contain
     deeply private data — minor's photos, medical info, etc.; ECHO
     should not load any of that into its in-memory event log)
  6. Retention — Cellebrite extractions become evidence and have
     their own chain-of-custody retention; ECHO references them but
     never stores copies
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


# ── Event types derived from a Cellebrite extraction ──────────────
@dataclass
class CellebriteCall:
    timestamp: datetime
    direction: str                  # "in" | "out" | "missed"
    counterpart_number: str
    counterpart_name: Optional[str] # from device's contact list if available
    duration_sec: int
    source_device_imei: str         # the seized phone's IMEI
    case_id: str                    # SIU case this extraction belongs to
    ufdr_path: str                  # reference to source UFDR for chain-of-custody

@dataclass
class CellebriteMessage:
    timestamp: datetime
    direction: str                  # "in" | "out"
    counterpart_number: Optional[str]
    counterpart_app_handle: Optional[str]  # WhatsApp/Signal/etc. handle
    app_name: str                   # "SMS" | "WhatsApp" | "Signal" | "Telegram" | ...
    snippet_hash: str               # SHA256 of message text — actual text stays in evidence
    media_attached: bool
    source_device_imei: str
    case_id: str
    ufdr_path: str

@dataclass
class CellebriteLocation:
    timestamp: datetime
    lat: float
    lng: float
    accuracy_m: float
    source: str                     # "exif" | "google_maps" | "app_ping" | ...
    source_device_imei: str
    case_id: str
    ufdr_path: str

@dataclass
class CellebriteAppData:
    timestamp: datetime
    app_name: str                   # "DJI Fly" | "Cash App" | "FB Messenger" | ...
    event_type: str                 # "login" | "transaction" | "drone_flight" | ...
    summary: str                    # short description
    counterpart: Optional[str]
    amount_usd: Optional[float]     # for financial apps
    source_device_imei: str
    case_id: str
    ufdr_path: str


class CellebriteConnector:
    """PLACEHOLDER — watches UFDR drop dir, parses extractions, emits events.

    Heavyweight workflow — parsing a single UFDR can take 1-5 minutes
    and produce thousands of events. Runs as a background worker that
    processes one UFDR at a time, marking processed files with a
    .processed sidecar so they aren't re-ingested.
    """

    def __init__(self,
                 ufdr_drop_dir: str,
                 credentials: dict,
                 on_call: Callable[[CellebriteCall], None],
                 on_message: Callable[[CellebriteMessage], None],
                 on_location: Callable[[CellebriteLocation], None],
                 on_app_data: Callable[[CellebriteAppData], None]):
        self.ufdr_drop_dir = ufdr_drop_dir   # PLACEHOLDER — committee provides
        self.credentials = credentials       # PLACEHOLDER — secrets manager
        self.on_call = on_call
        self.on_message = on_message
        self.on_location = on_location
        self.on_app_data = on_app_data

    def start(self) -> None:
        """PLACEHOLDER — start the UFDR watcher thread."""
        pass

    def stop(self) -> None:
        pass

    def process_ufdr(self, ufdr_path: str, case_id: str) -> dict:
        """PLACEHOLDER — parse a single UFDR file using the committee-chosen
        parser library (Cellebrite Reader SDK / ufed2json / ALEAPP / plaso).

        Returns a summary dict with counts:
          {"calls": N, "messages": N, "locations": N, "app_events": N}
        """
        return {"calls": 0, "messages": 0, "locations": 0, "app_events": 0}
