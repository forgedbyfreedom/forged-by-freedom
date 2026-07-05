"""
ECHO Multi-Camera Orchestrator.

REAL implementation — top-level entry point for the correctional
deployment. Loads echo_cameras.yaml, spins up:
  • One EchoEngine + RtspAudioSource per camera that has_audio
  • One VisionWorker per camera that has_video (PLACEHOLDER — wires
    up but doesn't run inference until echo_vision is filled in)
  • One FaceRecognitionWorker per camera that has_video (PLACEHOLDER)
  • One ZoneEngine that evaluates all face-detection events
  • One CorrelationEngine that ingests EVERY event type
  • Integration connectors for ViaPath + Tecore (PLACEHOLDER stubs
    until vendor API credentials available)

All events fan into the correlation engine, which emits a
CorrelationReport whenever a drone is detected, naming the inmate
and external-contact candidates ranked by score.

Run:
  python echo_multi.py --config echo_cameras.yaml
"""
from __future__ import annotations

import argparse
import json
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Local imports — relative when run as module, absolute when CLI
try:
    from .echo_engine import EchoEngine
    from .echo_rtsp import RtspAudioSource
    from .echo_vision import VisionWorker, VisionDetection
    from .echo_face import FaceRecognitionWorker
    from .echo_zones import ZoneEngine, InmateLocation
    from .echo_correlation import CorrelationEngine, Event, CorrelationReport
    from .echo_viapath import ViaPathConnector
    from .echo_tecore import TecoreConnector
    from .echo_alerts import dispatch_alert
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from echo_engine import EchoEngine
    from echo_rtsp import RtspAudioSource
    from echo_vision import VisionWorker, VisionDetection
    from echo_face import FaceRecognitionWorker
    from echo_zones import ZoneEngine, InmateLocation
    from echo_correlation import CorrelationEngine, Event, CorrelationReport
    from echo_viapath import ViaPathConnector
    from echo_tecore import TecoreConnector
    from echo_alerts import dispatch_alert


# ── Camera record (live state) ─────────────────────────────────────
class CameraRunner:
    """Per-camera bundle of engine, RTSP source, vision/face workers."""

    def __init__(self, cfg: dict, zone_engine: ZoneEngine,
                 correlation: CorrelationEngine,
                 inmate_db_path: str):
        self.cfg = cfg
        self.camera_id = cfg["id"]
        self.zone_ids = cfg.get("zone_ids", [])
        self.zone_engine = zone_engine
        self.correlation = correlation

        # ── Audio path (REAL — works today) ──────────────────
        if cfg.get("has_audio", False):
            self.audio_engine = EchoEngine()
            self.audio_source = RtspAudioSource(
                rtsp_url=cfg["rtsp"],
                on_block=self._on_audio_block,
                camera_name=cfg["id"],
            )
        else:
            self.audio_engine = None
            self.audio_source = None

        # ── Vision path (PLACEHOLDER — wires up, no inference yet) ──
        if cfg.get("has_video", False):
            self.vision = VisionWorker(
                rtsp_url=cfg["rtsp"],
                camera_id=cfg["id"],
                on_detection=self._on_vision_detection,
                enabled_detectors=("drone", "phone"),
            )
            self.face = FaceRecognitionWorker(
                camera_id=cfg["id"],
                inmate_db_path=inmate_db_path,
                on_inmate_seen=self._on_inmate_seen,
            )
        else:
            self.vision = None
            self.face = None

        self.last_score = 0.0
        self.last_score_time: datetime = datetime.now()
        self.detection_count = 0
        self._health = None

    def start(self) -> None:
        # Register in the health registry — mark OK on first audio block
        try:
            from echo_health import REGISTRY as _HR
            _HR.register(f"camera:{self.camera_id}",
                         role="camera",
                         has_audio=bool(self.audio_source),
                         has_video=bool(self.vision))
            self._health = _HR
        except Exception:
            self._health = None
        if self.audio_source:
            self.audio_source.start()
        if self.vision:
            self.vision.start()

    def stop(self) -> None:
        if self.audio_source:
            self.audio_source.stop()
        if self.vision:
            self.vision.stop()
        if self._health:
            self._health.report_down(f"camera:{self.camera_id}", "stopped")

    # ── audio detection callback ─────────────────────────────
    def _on_audio_block(self, audio):
        if not self.audio_engine:
            return
        # Fault isolation: any error in engine.process must not take
        # down the audio thread. Log + demote to DEGRADED, keep going.
        try:
            result = self.audio_engine.process(audio)
        except Exception as exc:
            if self._health:
                self._health.report_degraded(
                    f"camera:{self.camera_id}",
                    f"engine.process failed: {type(exc).__name__}: {exc}",
                )
            return
        # Successful tick → report OK (also promotes "acoustic" subsystem)
        if self._health:
            self._health.report_ok(f"camera:{self.camera_id}")
            self._health.report_ok("acoustic")
        score = float(result.get("score", 0.0)) if isinstance(result, dict) else 0.0
        self.last_score = score
        self.last_score_time = datetime.now()
        if isinstance(result, dict) and result.get("detected"):
            self.detection_count += 1
            self.correlation.ingest(Event(
                source="drone_audio",
                timestamp=datetime.now(),
                payload={
                    "camera_id": self.camera_id,
                    "zone_ids": self.zone_ids,
                    "confidence": score,
                    "feature_summary": result.get("summary", ""),
                },
            ))
            dispatch_alert("drone_detected", {
                "camera": self.camera_id,
                "score": score,
                "method": "audio",
            })

    # ── vision detection callback (called by echo_vision PLACEHOLDER) ──
    def _on_vision_detection(self, det: VisionDetection) -> None:
        source = ("drone_visual" if det.object_class == "drone"
                  else f"vision_{det.object_class}")
        self.correlation.ingest(Event(
            source=source,
            timestamp=datetime.fromtimestamp(det.timestamp),
            payload={
                "camera_id": self.camera_id,
                "zone_ids": self.zone_ids,
                "object_class": det.object_class,
                "confidence": det.confidence,
                "bbox": det.bbox,
            },
        ))
        if det.object_class == "drone" and det.confidence >= 0.6:
            dispatch_alert("drone_detected", {
                "camera": self.camera_id,
                "score": det.confidence,
                "method": "visual",
            })
        elif det.object_class == "phone":
            dispatch_alert("phone_in_inmate_hand", {
                "camera": self.camera_id,
                "score": det.confidence,
            })
        elif det.object_class == "violence":
            dispatch_alert("violence_imminent", {
                "camera": self.camera_id,
                "score": det.confidence,
            })

    # ── face recognition callback (called by echo_face PLACEHOLDER) ──
    def _on_inmate_seen(self, obs: InmateLocation) -> None:
        violations = self.zone_engine.evaluate(obs)
        for v in violations:
            self.correlation.ingest(Event(
                source="zone_violation",
                timestamp=datetime.fromtimestamp(obs.timestamp),
                payload={
                    "inmate_id": v.inmate_id,
                    "zone_id": v.zone_id,
                    "zone_name": v.zone_name,
                    "reason": v.reason,
                    "camera_id": self.camera_id,
                },
            ))
            dispatch_alert("inmate_out_of_bounds", {
                "inmate_id": v.inmate_id,
                "zone": v.zone_name,
                "reason": v.reason,
                "camera": self.camera_id,
            })
        # Always feed the location event into correlation for later cross-
        # referencing with drone detections
        self.correlation.ingest(Event(
            source="face",
            timestamp=datetime.fromtimestamp(obs.timestamp),
            payload={
                "inmate_id": obs.inmate_id,
                "camera_id": self.camera_id,
                "zone_ids": obs.zone_ids,
                "face_confidence": obs.face_confidence,
                "zone_type": "outdoor_yard" if any(
                    self.zone_engine.zones.get(zid, None) and
                    self.zone_engine.zones[zid].type in ("outdoor_yard", "perimeter")
                    for zid in obs.zone_ids) else "indoor",
            },
        ))

    # ── status ───────────────────────────────────────────────
    def status(self) -> dict:
        s: dict[str, Any] = {
            "camera_id": self.camera_id,
            "zone_ids": self.zone_ids,
            "audio_health": self.audio_source.health() if self.audio_source else None,
            "last_score": self.last_score,
            "last_score_age_sec": (datetime.now() - self.last_score_time).total_seconds(),
            "detection_count": self.detection_count,
        }
        return s


# ── Orchestrator ────────────────────────────────────────────────────
class EchoMulti:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._stop_event = threading.Event()
        self._reload_lock = threading.Lock()

        # CORTEX correlation engine (fusion) + pipeline state machine
        try:
            from echo_config import CFG
            _min_sensors = CFG["correlation"].get("min_viable_sensors", 2)
            _window_h    = CFG["correlation"].get("window_hours", 4)
            _alert_floor = CFG["correlation"].get("alert_score_floor", 0.5)
        except Exception:
            _min_sensors, _window_h, _alert_floor = 2, 4, 0.5

        self.zone_engine = ZoneEngine(config_path)
        self.correlation = CorrelationEngine(
            window_hours=_window_h,
            on_report=self._on_correlation_report,
            min_viable_sensors=_min_sensors,
        )

        # Bind the state machine to the correlation engine.
        # Auto-transitions: drone event → SCANNING → TRACKING;
        # correlation report ≥ alert_floor → ALERT.
        try:
            from echo_state import PipelineStateMachine, bind_to_correlation_engine
            self.state = PipelineStateMachine()
            bind_to_correlation_engine(self.state, self.correlation,
                                       alert_score_floor=_alert_floor)
        except Exception as exc:
            print(f"[echo-multi] state machine unavailable: {exc}")
            self.state = None

        self.cameras: dict[str, CameraRunner] = {}

        self.viapath: ViaPathConnector | None = None
        self.tecore: TecoreConnector | None = None
        self._reload()

    def _reload(self) -> None:
        with self._reload_lock, open(self.config_path) as f:
            cfg = yaml.safe_load(f) or {}
        self.zone_engine.reload()

        inmate_db_path = cfg.get("face_db_path", "/var/echo/inmate_faces.db")

        wanted_ids = {c["id"] for c in cfg.get("cameras", [])}
        # Stop cameras that were removed
        for cid in list(self.cameras.keys()):
            if cid not in wanted_ids:
                self.cameras[cid].stop()
                del self.cameras[cid]
        # Start/update cameras
        for ccfg in cfg.get("cameras", []):
            if ccfg["id"] not in self.cameras:
                runner = CameraRunner(ccfg, self.zone_engine,
                                      self.correlation, inmate_db_path)
                self.cameras[ccfg["id"]] = runner
                runner.start()
                print(f"[echo-multi] started camera {ccfg['id']}")

    def _on_correlation_report(self, report: CorrelationReport) -> None:
        print(f"\n{'─' * 60}")
        print(f"DRONE DETECTED on {report.drone_camera} @ {report.drone_timestamp.isoformat()}")
        print(f"  audio/visual confidence: {report.drone_confidence:.2f}")
        if report.inmate_candidates:
            print(f"\n  Top inmate candidates:")
            for c in report.inmate_candidates[:5]:
                print(f"    {c.score:.2f}  {c.subject_id} ({c.subject_name or 'unknown'})")
                for sig, sc in c.signal_scores.items():
                    print(f"        ├─ {sig}: {sc:.2f}")
        else:
            print(f"\n  No inmate candidates correlated.")
        if report.external_candidates:
            print(f"\n  Top external-contact candidates:")
            for c in report.external_candidates[:5]:
                print(f"    {c.score:.2f}  {c.subject_id} ({c.subject_name or 'unknown'})")
        print(f"{'─' * 60}\n")

        # Strongest combined signal = HIGHEST severity alert
        if (report.inmate_candidates and report.inmate_candidates[0].score >= 0.5) \
                or (report.external_candidates and report.external_candidates[0].score >= 0.5):
            dispatch_alert("drone_with_correlated_inmate", {
                "drone_camera": report.drone_camera,
                "top_inmate": report.inmate_candidates[0].subject_id if report.inmate_candidates else None,
                "top_contact": report.external_candidates[0].subject_id if report.external_candidates else None,
            })

    def start(self) -> None:
        # PLACEHOLDER — wire up vendor connectors when credentials available
        # self.viapath = ViaPathConnector(mode="rest", credentials=...,
        #                                  on_call=lambda c: self.correlation.ingest(...),
        #                                  ...)
        # self.viapath.start()
        # self.tecore = TecoreConnector(mode="syslog", credentials=...,
        #                                on_capture=lambda c: self.correlation.ingest(...))
        # self.tecore.start()
        # Optional REST API — starts only if config.yaml has api.enabled=true
        try:
            from echo_api import maybe_start_api
            maybe_start_api(engine=self.correlation, orchestrator=self)
        except Exception as exc:                          # never block startup on API failure
            print(f"[echo-multi] API bootstrap skipped: {exc}")

        signal.signal(signal.SIGINT, self._on_sigint)
        signal.signal(signal.SIGTERM, self._on_sigint)
        print(f"[echo-multi] {len(self.cameras)} cameras running. Ctrl+C to stop.")
        try:
            while not self._stop_event.is_set():
                time.sleep(10)
                # PLACEHOLDER — opportunity for periodic config reload, health check, etc.
        except KeyboardInterrupt:
            pass
        self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        for runner in self.cameras.values():
            runner.stop()
        if self.viapath:
            self.viapath.stop()
        if self.tecore:
            self.tecore.stop()
        print("[echo-multi] all workers stopped.")

    def _on_sigint(self, signum, frame):
        self._stop_event.set()

    def status_snapshot(self) -> dict:
        return {
            "cameras": {cid: r.status() for cid, r in self.cameras.items()},
            "correlation_events_in_window": len(self.correlation._events),
        }


def main():
    p = argparse.ArgumentParser(description="ECHO Multi-Camera Orchestrator")
    p.add_argument("--config", default="echo/echo_cameras.yaml")
    args = p.parse_args()
    EchoMulti(args.config).start()


if __name__ == "__main__":
    main()
