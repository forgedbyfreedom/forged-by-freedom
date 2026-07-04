"""
ECHO Acoustic Lily Pads — distributed low-cost acoustic sensor network.

────────────────────────────────────────────────────────────────────────
INSPIRATION — Ukraine "Sky Fortress"

In 2023 the Ukrainian volunteer group Sky Fortress deployed thousands of
low-cost networked acoustic sensors — cheap microphones on smartphones,
Raspberry Pis, and dedicated boards — spread across the country. Each
node listens for the distinctive drone signature and reports timestamped
detections upstream. The network fuses them into engagement-quality
tracks against Shahed/Geran-136 attack drones for a fraction of the
cost of traditional radar.

The core insight: **one microphone is a detector; many microphones,
time-synchronized, are a tracking radar**. The math is time-difference-
of-arrival (TDOA): if node A hears the drone at t=0.000 and node B
(500 m away) hears it at t=0.412, then the drone lies on a hyperbola of
constant range difference between A and B. Three nodes give you a
position fix; four give you altitude too.

────────────────────────────────────────────────────────────────────────
WHY THIS MATTERS FOR CORRECTIONS

A single ECHO camera microphone catches drones at ~300 m in favorable
conditions. Facility-wide coverage means either buying commercial
radar (~$500k+) or spreading many cheap ears. Sky Fortress-style lily
pads scale the second way:

  • Per-node cost: $30-100 (Raspberry Pi + USB mic + PoE) — orders of
    magnitude cheaper than one Dedrone RfPatrol sensor
  • 20 lily pads around a facility perimeter + housing yards gives
    ~500 m radius coverage each, overlapping into full-facility
    triangulation
  • Nodes run the SAME echo_engine.py detection pipeline as the
    camera-attached mics — no new detection ML needed
  • TDOA fusion here produces (x, y, z, t, confidence) tracks that
    let the correlation engine ask "which YARD was the drone over"
    instead of just "one camera heard something"

Cross-facility federation:
  If SC DOC deploys ECHO at every institution, lily pad networks at
  each site can share detections through a central federation service.
  A drone that hits Broad River and lifts off toward Kirkland becomes
  a single tracked event across facilities — useful for post-incident
  investigation and for prosecuting the operator across jurisdictions.

────────────────────────────────────────────────────────────────────────
HARDWARE SPEC — per lily pad node

Minimum viable:
  Raspberry Pi 4B (2 GB)                    $45
  USB electret mic (or PoE Dante mic)       $25
  PoE HAT + injector                        $30
  Weatherproof IP66 enclosure               $30
  Windscreen (foam) for outdoor use         $10
  → $140 per node, ~$3k for 20-node facility coverage

Recommended (better sensitivity + GPS-disciplined clock):
  Raspberry Pi 5 (4 GB)                     $60
  MEMS mic array HAT (ReSpeaker 6-mic)      $80
  GPS PPS module (NEO-M8T + antenna)        $35
  PoE HAT + injector                        $30
  IP66 enclosure                            $40
  → $245 per node
  → PPS synchronizes clocks to ±100 ns — the timing precision TDOA
    needs to keep position error under a meter at 300 m range

For very high accuracy or beamforming:
  RØDE / Sennheiser-grade outdoor mic       $200
  4-mic array with known geometry           $150
  → $500+ per node, only for critical
    perimeter posts (front gate, receiving)

────────────────────────────────────────────────────────────────────────
CLOCK SYNC — the critical part

TDOA precision needs clock sync ≤ 1 ms (worse and position error
blows up to hundreds of meters). Options:

  (1) GPS PPS at every node    ~100 ns precision. Best.
  (2) PTP (IEEE 1588) over
      wired PoE                ~1 μs precision. Good if the switches
                               support hardware PTP timestamping.
  (3) NTP over LAN             ~1-10 ms precision. Adequate for
                               COARSE tracking (~10 m error at 300 m),
                               NOT for meter-scale.
  (4) Raw audio cross-correlation
      against a shared beacon  workaround for cheap nodes — periodic
                               ultrasonic ping (>18 kHz) from a
                               known-position beacon lets nodes
                               resynchronize by cross-correlating.

Recommended: (2) PTP for wired lily pads on facility LAN, (1) GPS PPS
for any wireless / battery / remote nodes.

────────────────────────────────────────────────────────────────────────
NETWORKING

Each node → central lily pad aggregator (this file's `LilyPadHub`)
over a lightweight publish channel. Options:

  MQTT      canonical for IoT fleets; nice retention/QoS knobs
  gRPC      streaming, low overhead, works well over TLS
  Kafka     over-engineered for a facility; right for federation
            across many facilities
  HTTP POST simplest; buffer + retry per node

The hub:
  • Buffers detections in a small time-window (default 3 s)
  • Groups detections that arrived within TDOA_MATCH_MS of each other
  • Runs `tdoa_solve()` to produce an (x, y, z) fix
  • Emits a `LilyPadTrack` (see below) into echo_correlation as a
    high-confidence `drone_audio` event with position

────────────────────────────────────────────────────────────────────────
LEGAL / POLICY

  • Ambient outdoor audio around a facility perimeter has a
    diminished-privacy expectation, but recording VOICES near the fence
    (staff, visitor lot, public sidewalk) may implicate state wiretap
    laws. SC is a one-party-consent state, so facility-owned areas are
    fine, but signage should note audio surveillance.
  • ECHO's classifier only stores DETECTIONS, not audio, by default —
    tune false-positive suppression to keep it that way for lily pads
    facing public sidewalks. See INTEGRATION_CHECKLIST.md § 5h retention.
  • Cross-facility federation crosses agency policy lines; run
    federation through a shared central service the DOC controls,
    not peer-to-peer between sites.

────────────────────────────────────────────────────────────────────────
TO COMPLETE — committee / RF+network tech must provide:
  1. Node hardware selection (basic Pi / GPS+array / pro grade)
  2. Physical install locations + surveyed (x, y, z) coordinates
     in facility-local ENU meters (relative to a chosen origin)
  3. Clock sync stack (PTP / GPS PPS / NTP / beacon)
  4. Transport (MQTT broker URL / gRPC endpoint / HTTP POST target)
  5. Retention policy for raw audio (default: NONE — only detections)
  6. Federation with other facilities: ON / OFF and legal review
  7. Public-audio signage plan for perimeter nodes
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

log = logging.getLogger("echo.lily_pads")

SPEED_OF_SOUND_MPS = 343.0  # ~20 °C dry air; committee can tune per climate


# ── Data types ────────────────────────────────────────────────────
@dataclass
class LilyPadNode:
    """Physical / logical config for one distributed acoustic sensor."""
    node_id: str                     # short unique id, e.g. "lp-yard-a-nw"
    site_id: str                     # facility id (for federation)
    # Local ENU (east-north-up) coordinates in meters, relative to a
    # facility-local origin picked once by the committee. Do NOT use raw
    # WGS84 lat/lng for TDOA math — the meters conversion at every hop
    # kills numerical precision.
    x_m: float
    y_m: float
    z_m: float
    clock_source: str = "ntp"        # "gps_pps" | "ptp" | "ntp" | "beacon"
    mic_type: str = "usb_electret"   # "usb_electret" | "mems_array" | "rode"
    label: Optional[str] = None      # human-friendly ("SW yard corner")


@dataclass
class LilyPadDetection:
    """One drone-detection ping from one node."""
    node_id: str
    timestamp: datetime              # node-local, must be clock-synced
    confidence: float                # 0..1 from echo_engine
    signature: str                   # "drone_quad" | "drone_fixed_wing" | "drone_unknown"
    peak_frequency_hz: Optional[float] = None
    audio_snr_db: Optional[float] = None
    # Optional: node reports its clock-sync quality so hub can weight
    clock_sync_error_ms: Optional[float] = None
    raw: dict = field(default_factory=dict)


@dataclass
class LilyPadTrack:
    """Fused position estimate from N node detections."""
    track_id: str
    timestamp: datetime              # ~mean of contributing detections
    position_m: tuple[float, float, float]      # (x, y, z) facility ENU
    position_lat: Optional[float] = None        # if hub has geo-anchor
    position_lng: Optional[float] = None
    confidence: float = 0.0
    contributing_nodes: list[str] = field(default_factory=list)
    residual_m: float = 0.0          # solve residual — lower = tighter fix
    signature: str = "drone_unknown"
    raw_detections: list[LilyPadDetection] = field(default_factory=list)


# ── Hub ───────────────────────────────────────────────────────────
class LilyPadHub:
    """
    Central aggregator. Nodes call `ingest_detection()`; the hub
    time-groups detections and runs TDOA fusion to produce tracks.

    Wire the emitted tracks into echo_correlation as high-confidence
    `drone_audio` events (see `track_to_event()` at the bottom).
    """

    def __init__(
        self,
        nodes: list[LilyPadNode],
        on_track: Callable[[LilyPadTrack], None],
        *,
        tdoa_group_window_ms: int = 800,
        min_nodes_for_fix: int = 3,
        geo_anchor_lat: Optional[float] = None,
        geo_anchor_lng: Optional[float] = None,
        geo_anchor_bearing_deg: float = 0.0,
    ):
        if min_nodes_for_fix < 3:
            raise ValueError("min_nodes_for_fix must be ≥ 3 for 2D solve")
        self.nodes = {n.node_id: n for n in nodes}
        self.on_track = on_track
        self.tdoa_group_window = timedelta(milliseconds=tdoa_group_window_ms)
        self.min_nodes = min_nodes_for_fix
        self.geo_anchor = None
        if geo_anchor_lat is not None and geo_anchor_lng is not None:
            self.geo_anchor = (geo_anchor_lat, geo_anchor_lng,
                               geo_anchor_bearing_deg)

        self._pending: deque[LilyPadDetection] = deque()
        self._lock = threading.RLock()
        self._track_counter = 0

    # ── Node → Hub ─────────────────────────────────────────
    def ingest_detection(self, det: LilyPadDetection) -> None:
        if det.node_id not in self.nodes:
            log.warning("detection from unknown node %s", det.node_id)
            return
        with self._lock:
            self._pending.append(det)
            self._try_fuse()

    def flush(self) -> None:
        """Force-fuse any pending detections (call from a timer thread
        every ~200 ms in production to catch groups whose window closed
        without a new ingest triggering the check)."""
        with self._lock:
            self._try_fuse(force=True)

    # ── Fusion ─────────────────────────────────────────────
    def _try_fuse(self, force: bool = False) -> None:
        """
        Walk the pending deque, group detections whose timestamps are
        within tdoa_group_window, and solve if we have enough nodes.

        Waits for the group window to close before firing so late-arriving
        node detections don't miss the fuse. Set force=True (or call
        flush()) to fuse immediately regardless.
        """
        if not self._pending:
            return
        now = datetime.now()
        # Drop stragglers older than 5s (they can't fuse anymore)
        while self._pending and (now - self._pending[0].timestamp).total_seconds() > 5:
            self._pending.popleft()

        seed = self._pending[0]
        seed_age = (now - seed.timestamp).total_seconds()
        # Give slower nodes their chance to arrive
        if not force and seed_age < self.tdoa_group_window.total_seconds():
            return
        group = [d for d in self._pending
                 if abs((d.timestamp - seed.timestamp).total_seconds())
                    <= self.tdoa_group_window.total_seconds()]
        # Dedup: one detection per node per group (keep the earliest)
        by_node: dict[str, LilyPadDetection] = {}
        for d in group:
            existing = by_node.get(d.node_id)
            if existing is None or d.timestamp < existing.timestamp:
                by_node[d.node_id] = d
        group = list(by_node.values())

        if len(group) < self.min_nodes:
            return

        try:
            track = self._solve_tdoa(group)
        except Exception:
            log.exception("TDOA solve failed")
            return

        # Pop the fused detections
        for d in group:
            try:
                self._pending.remove(d)
            except ValueError:
                pass

        if track is not None:
            self.on_track(track)

    def _solve_tdoa(self, group: list[LilyPadDetection]) -> Optional[LilyPadTrack]:
        """
        Weighted-least-squares TDOA position solve.

        For each pair of nodes (i, j):
            (t_i - t_j) * c = |x - p_i| - |x - p_j|
        Linearize around a seed guess, iterate.

        Seed guess = centroid of contributing nodes.
        """
        pts = []
        times = []
        for d in group:
            n = self.nodes[d.node_id]
            pts.append((n.x_m, n.y_m, n.z_m))
            times.append(d.timestamp)
        t0 = min(times)
        toa = [(t - t0).total_seconds() for t in times]

        # Seed = centroid
        x = sum(p[0] for p in pts) / len(pts)
        y = sum(p[1] for p in pts) / len(pts)
        z = 30.0  # assume drone altitude ~30 m for seed (typical drop)

        # Gauss-Newton iterations
        max_iter = 20
        for _ in range(max_iter):
            # Residuals: r_ij = (toa_i - toa_j)*c - (|x-p_i| - |x-p_j|)
            # We regularize by taking pairs against node 0
            p0 = pts[0]
            r0 = math.sqrt((x - p0[0])**2 + (y - p0[1])**2 + (z - p0[2])**2)
            residuals = []
            for i in range(1, len(pts)):
                pi = pts[i]
                ri = math.sqrt((x - pi[0])**2 + (y - pi[1])**2 + (z - pi[2])**2)
                predicted = ri - r0
                measured = (toa[i] - toa[0]) * SPEED_OF_SOUND_MPS
                residuals.append(measured - predicted)
            # Simple gradient step (full Jacobian would be cleaner; this
            # is deliberately compact — swap in scipy.optimize.least_squares
            # in production if scipy is available).
            step = sum(residuals) / max(len(residuals), 1)
            if abs(step) < 0.05:
                break
            # Move toward the mean bearing of positive residuals
            gx = gy = 0.0
            for i, r in enumerate(residuals, start=1):
                pi = pts[i]
                dxi = x - pi[0]; dyi = y - pi[1]
                norm = math.hypot(dxi, dyi) or 1.0
                gx -= r * dxi / norm
                gy -= r * dyi / norm
            gnorm = math.hypot(gx, gy) or 1.0
            k = min(2.0, abs(step))
            x += k * gx / gnorm
            y += k * gy / gnorm

        # Residual at solution
        p0 = pts[0]
        r0 = math.sqrt((x - p0[0])**2 + (y - p0[1])**2 + (z - p0[2])**2)
        total_res = 0.0
        for i in range(1, len(pts)):
            pi = pts[i]
            ri = math.sqrt((x - pi[0])**2 + (y - pi[1])**2 + (z - pi[2])**2)
            predicted = ri - r0
            measured = (toa[i] - toa[0]) * SPEED_OF_SOUND_MPS
            total_res += (measured - predicted) ** 2
        residual_m = math.sqrt(total_res / max(len(pts) - 1, 1))

        confidence = _confidence_from_group(group, residual_m)
        if confidence < 0.1:
            log.debug("low-confidence fix, dropping (residual=%.1fm)", residual_m)
            return None

        self._track_counter += 1
        track = LilyPadTrack(
            track_id=f"lp-{int(time.time())}-{self._track_counter}",
            timestamp=t0 + timedelta(seconds=sum(toa) / len(toa)),
            position_m=(x, y, z),
            confidence=confidence,
            contributing_nodes=[d.node_id for d in group],
            residual_m=residual_m,
            signature=self._vote_signature(group),
            raw_detections=list(group),
        )
        if self.geo_anchor:
            track.position_lat, track.position_lng = self._enu_to_wgs84(x, y)
        return track

    def _vote_signature(self, group: list[LilyPadDetection]) -> str:
        counts: dict[str, int] = defaultdict(int)
        for d in group:
            counts[d.signature] += 1
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def _enu_to_wgs84(self, x: float, y: float) -> tuple[float, float]:
        """
        Approximate ENU→WGS84 conversion around the geo anchor.
        Good enough for facility-scale distances (<5 km).
        """
        lat0, lng0, bearing = self.geo_anchor
        # Rotate ENU by bearing to align with true north
        b = math.radians(bearing)
        e =  x * math.cos(b) + y * math.sin(b)
        n = -x * math.sin(b) + y * math.cos(b)
        # ~111,320 m per degree lat; scale lng by cos(lat)
        dlat = n / 111_320.0
        dlng = e / (111_320.0 * max(math.cos(math.radians(lat0)), 0.01))
        return (lat0 + dlat, lng0 + dlng)


def _confidence_from_group(group: list[LilyPadDetection],
                           residual_m: float) -> float:
    """
    Composite confidence:
      • average per-node detection confidence
      • node count bonus (more nodes = tighter fix)
      • residual penalty (larger residual = worse geometry / bad sync)
      • clock-sync penalty (nodes on NTP get discounted)
    """
    avg_conf = sum(d.confidence for d in group) / len(group)
    node_bonus = min(0.3, 0.05 * (len(group) - 3))     # +0.05 per node beyond 3, cap +0.3
    residual_penalty = min(0.5, residual_m / 200.0)    # 100 m residual → 0.5 penalty
    sync_penalty = 0.0
    for d in group:
        if d.clock_sync_error_ms and d.clock_sync_error_ms > 5:
            sync_penalty += 0.02
    sync_penalty = min(0.3, sync_penalty)
    conf = avg_conf + node_bonus - residual_penalty - sync_penalty
    return max(0.0, min(1.0, conf))


# ── Correlation-engine bridge ─────────────────────────────────────
def track_to_event(track: LilyPadTrack, camera_id: str = "lily_pad_network"):
    """
    Convert a fused lily-pad track into an echo_correlation.Event with
    source='drone_audio' so it triggers a full correlation pass.

    Wire in echo_multi.py:
        hub = LilyPadHub(nodes=NODES,
                         on_track=lambda t: engine.ingest(track_to_event(t)))
    """
    from echo_correlation import Event
    return Event(
        source="drone_audio",
        timestamp=track.timestamp,
        payload={
            "camera_id": camera_id,
            "track_id": track.track_id,
            "confidence": track.confidence,
            "position_m": track.position_m,
            "position_lat": track.position_lat,
            "position_lng": track.position_lng,
            "residual_m": track.residual_m,
            "contributing_nodes": track.contributing_nodes,
            "signature": track.signature,
            "source_kind": "lily_pad_tdoa",  # so dashboard can badge these
        },
    )


# ── Convenience: node-side helper ────────────────────────────────
def make_detection_from_echo(node_id: str, echo_result: dict,
                             now: Optional[datetime] = None) -> LilyPadDetection:
    """
    Called on the node side after echo_engine produces a detection.
    Wraps it into a LilyPadDetection to POST to the hub.

    echo_result is expected to have: confidence, signature,
    peak_frequency_hz (optional), audio_snr_db (optional).
    """
    return LilyPadDetection(
        node_id=node_id,
        timestamp=now or datetime.now(),
        confidence=float(echo_result.get("confidence", 0.0)),
        signature=str(echo_result.get("signature", "drone_unknown")),
        peak_frequency_hz=echo_result.get("peak_frequency_hz"),
        audio_snr_db=echo_result.get("audio_snr_db"),
        raw=echo_result,
    )


if __name__ == "__main__":
    # Quick self-test with a simulated 4-node array and a synthetic
    # source at (100, 50, 30).
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    NODES = [
        LilyPadNode(node_id="lp-nw", site_id="test", x_m=0,   y_m=0,   z_m=5,
                    clock_source="gps_pps", label="NW yard corner"),
        LilyPadNode(node_id="lp-ne", site_id="test", x_m=200, y_m=0,   z_m=5,
                    clock_source="gps_pps", label="NE yard corner"),
        LilyPadNode(node_id="lp-sw", site_id="test", x_m=0,   y_m=150, z_m=5,
                    clock_source="gps_pps", label="SW yard corner"),
        LilyPadNode(node_id="lp-se", site_id="test", x_m=200, y_m=150, z_m=5,
                    clock_source="gps_pps", label="SE yard corner"),
    ]

    src = (100.0, 50.0, 30.0)
    t_ref = datetime.now()

    def _print_track(t: LilyPadTrack) -> None:
        print(f"[LP-track] pos=({t.position_m[0]:.1f}, {t.position_m[1]:.1f}, "
              f"{t.position_m[2]:.1f}) conf={t.confidence:.2f} "
              f"residual={t.residual_m:.2f}m nodes={len(t.contributing_nodes)}")

    hub = LilyPadHub(NODES, on_track=_print_track)

    # Feed simulated detections with correct time-of-arrival
    for n in NODES:
        d_m = math.sqrt((n.x_m - src[0])**2 + (n.y_m - src[1])**2 + (n.z_m - src[2])**2)
        tof = d_m / SPEED_OF_SOUND_MPS
        hub.ingest_detection(LilyPadDetection(
            node_id=n.node_id,
            timestamp=t_ref + timedelta(seconds=tof),
            confidence=0.85,
            signature="drone_quad",
            clock_sync_error_ms=0.1,
        ))
    # Force-fuse now that all 4 nodes have arrived
    hub.flush()
    print(f"expected pos ~= ({src[0]}, {src[1]}, {src[2]})")
    print("(exact fix quality depends on solver — this file's compact "
          "Gauss-Newton is a placeholder; swap in scipy.optimize.least_squares "
          "for production accuracy.)")
