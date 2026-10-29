"""
ECHO Facial Recognition — integration with the committee's in-house FR system.

────────────────────────────────────────────────────────────────────────
INTEGRATION POINT — NOT a from-scratch facial-recognition build.

The committee has already developed and deployed the facial recognition
system. This module is the *client* — it wraps the committee's FR
service so ECHO's correlation + zone engines can consume its output.

────────────────────────────────────────────────────────────────────────
TO COMPLETE — committee must provide (see INTEGRATION_CHECKLIST.md):

  1. Integration mode — one of:
       • REST API (POST a frame, get JSON back) ── most common
       • Python library (import and call)        ── tightest performance
       • gRPC service (structured RPC)            ── enterprise-grade
       • File watcher (drop frame, pick up result) ── air-gapped
  2. Endpoint URL / library import path / gRPC stub / watched directory
  3. Authentication — bearer token / mTLS cert / API key / IP allowlist
  4. Request payload shape — what frame format does it accept?
     (JPEG bytes, PNG bytes, raw RGB numpy, base64-encoded, etc.)
  5. Response payload shape — what does a match look like?
     (we need: inmate_id, classification, confidence, bbox)
  6. Non-inmate handling — does the committee's system already redact
     staff/visitor faces? If not, what does it return for non-matches?

Once those six items are answered, the only file that changes is the
single _call_committee_fr() method below. Everything else in ECHO
already speaks the InmateLocation / StaffOrVisitorFace contract.
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

# Canonical InmateLocation type lives in echo_zones — re-exported here.
# Support both package-style (`from echo.echo_face import ...`) and
# script-style (`cd echo && python echo_multi.py ...`) invocation.
try:
    from .echo_zones import InmateLocation  # noqa: F401
except ImportError:  # standalone / script mode
    from echo_zones import InmateLocation  # noqa: F401


# ── Output shapes (consumed by echo_zones + echo_correlation) ──────
@dataclass
class FaceMatch:
    inmate_id: str
    classification: str             # "GP" | "GP-low" | "AdSeg" | etc.
    confidence: float               # 0..1 cosine similarity
    bbox: tuple                     # (x, y, w, h) in pixel coords


@dataclass
class StaffOrVisitorFace:
    """A non-inmate face. Stored only as anonymized bbox + timestamp.
    NO embedding generated for non-inmates. See ARCHITECTURE.md §
    Legal & policy."""
    bbox: tuple
    timestamp: float


# ── Integration client (committee FR system) ───────────────────────
class FaceRecognitionClient:
    """Generic interface that wraps the committee's FR system.

    Default implementation does nothing (returns no matches) so ECHO
    runs without errors even when the FR backend isn't wired yet. Once
    the committee provides the six items above, fill in
    _call_committee_fr() and switch DEFAULT_MODE to the right value.
    """

    DEFAULT_MODE = "rest"           # "rest" | "library" | "grpc" | "file"

    def __init__(self,
                 mode: Optional[str] = None,
                 endpoint: Optional[str] = None,
                 auth_token: Optional[str] = None,
                 timeout_sec: float = 1.5):
        self.mode = mode or self.DEFAULT_MODE
        self.endpoint = endpoint   # PLACEHOLDER — committee URL / import path / file dir
        self.auth_token = auth_token  # PLACEHOLDER — loaded from secrets manager, NEVER inline
        self.timeout_sec = timeout_sec
        # Track health for the dashboard
        self.total_calls = 0
        self.total_failures = 0
        self.last_call_time = 0.0

    # ── PRIMARY ENTRYPOINT — called by echo_vision / echo_multi ───
    def identify(self,
                 frame_jpeg: bytes,
                 camera_id: str) -> tuple[list[FaceMatch],
                                          list[StaffOrVisitorFace]]:
        """Submit a frame to the committee FR system.
        Returns (inmate_matches, non_inmate_faces).
        """
        self.total_calls += 1
        self.last_call_time = time.time()
        try:
            return self._call_committee_fr(frame_jpeg, camera_id)
        except Exception as e:
            self.total_failures += 1
            print(f"[face] FR call failed for {camera_id}: {e}")
            return [], []

    # ── PLACEHOLDER — the only method that needs real implementation ─
    def _call_committee_fr(self,
                           frame_jpeg: bytes,
                           camera_id: str) -> tuple[list[FaceMatch],
                                                    list[StaffOrVisitorFace]]:
        """COMMITTEE FILLS THIS IN.

        Suggested implementations for each mode (uncomment + adapt):

        # ── REST API ───────────────────────────────────────────────
        # import requests
        # r = requests.post(
        #     self.endpoint,
        #     headers={"Authorization": f"Bearer {self.auth_token}"},
        #     files={"frame": ("frame.jpg", frame_jpeg, "image/jpeg")},
        #     data={"camera_id": camera_id},
        #     timeout=self.timeout_sec,
        # )
        # r.raise_for_status()
        # return self._parse_response(r.json())

        # ── Python library ─────────────────────────────────────────
        # from committee_fr import classify
        # raw = classify(frame_jpeg, camera_id=camera_id)
        # return self._parse_response(raw)

        # ── gRPC ───────────────────────────────────────────────────
        # from committee_fr_pb2 import IdentifyRequest
        # from committee_fr_pb2_grpc import FRStub
        # req = IdentifyRequest(frame=frame_jpeg, camera_id=camera_id)
        # raw = self._grpc_stub.Identify(req, timeout=self.timeout_sec)
        # return self._parse_response(raw)

        # ── File-watcher (air-gapped) ──────────────────────────────
        # write frame to drop dir, poll results dir, parse on hit
        """
        return [], []  # safe no-op until wired

    def _parse_response(self, raw: dict) -> tuple[list[FaceMatch],
                                                  list[StaffOrVisitorFace]]:
        """Convert the committee's response shape to ECHO's canonical
        FaceMatch / StaffOrVisitorFace types.

        ASSUMED RESPONSE SHAPE (committee must confirm or override):
          {
            "matches": [
              {"inmate_id": "I-12345", "classification": "GP",
               "confidence": 0.87, "bbox": [x, y, w, h]},
              ...
            ],
            "non_matches": [
              {"bbox": [x, y, w, h]},
              ...
            ]
          }
        """
        now = time.time()
        matches = [
            FaceMatch(
                inmate_id=m["inmate_id"],
                classification=m.get("classification", "unknown"),
                confidence=float(m["confidence"]),
                bbox=tuple(m["bbox"]),
            )
            for m in raw.get("matches", [])
        ]
        non_matches = [
            StaffOrVisitorFace(bbox=tuple(nm["bbox"]), timestamp=now)
            for nm in raw.get("non_matches", [])
        ]
        return matches, non_matches

    def health(self) -> dict:
        return {
            "mode": self.mode,
            "endpoint": self.endpoint,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "failure_rate": (self.total_failures / self.total_calls
                             if self.total_calls else 0.0),
            "last_call_age_sec": (time.time() - self.last_call_time
                                  if self.last_call_time else None),
        }


# ── Worker (called by echo_multi per camera) ───────────────────────
class FaceRecognitionWorker:
    """Adapter between echo_vision's frame stream and the committee
    FR client. Emits InmateLocation events into echo_zones for
    permission checks + into echo_correlation for link analysis."""

    def __init__(self,
                 camera_id: str,
                 zone_ids: list[str],
                 client: FaceRecognitionClient,
                 on_inmate_seen: Callable[[InmateLocation], None]):
        self.camera_id = camera_id
        self.zone_ids = zone_ids
        self.client = client
        self.on_inmate_seen = on_inmate_seen

    def process_frame(self,
                      frame_jpeg: bytes) -> tuple[list[FaceMatch],
                                                  list[StaffOrVisitorFace]]:
        """Submit a frame and fan matches out to the orchestrator."""
        matches, non_matches = self.client.identify(frame_jpeg, self.camera_id)
        now = time.time()
        for m in matches:
            self.on_inmate_seen(InmateLocation(
                inmate_id=m.inmate_id,
                inmate_classification=m.classification,
                camera_id=self.camera_id,
                zone_ids=self.zone_ids,
                timestamp=now,
                face_confidence=m.confidence,
            ))
        return matches, non_matches
