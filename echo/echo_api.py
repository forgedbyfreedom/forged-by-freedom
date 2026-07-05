"""
ECHO REST API — optional, toggleable FastAPI service.

Exposes a small operational surface on top of a running EchoMulti /
correlation engine so ops tooling, dashboards, and SIEMs can:

    GET  /health              liveness probe (200 = process alive)
    GET  /status              pipeline state + per-subsystem health
    GET  /detections?since=…  recent events (ISO8601 or unix seconds cursor)
    POST /scan                trigger an on-demand correlation pass

DEFAULT: disabled. Headless deployments (single-mic property use,
lab setups) never need it. To enable:

    api:
      enabled: true
      host: 127.0.0.1        # or 0.0.0.0 to expose on LAN
      port: 5058
      bearer_token: "..."     # REQUIRED when host != 127.0.0.1

Then:

    python -m uvicorn echo.echo_api:app --host 127.0.0.1 --port 5058
    # or bootstrap in-process from echo_multi.py:
    from echo_api import maybe_start_api
    maybe_start_api(engine=engine, orchestrator=echo_multi_instance)

Security:
    • ANY host other than 127.0.0.1 requires bearer_token in config.
      The service refuses to start otherwise.
    • Rate-limit / IP-allow via a reverse proxy in front (nginx/Caddy);
      don't expose this directly to the internet.
    • POST /scan is opt-in-able (api.allow_scan_trigger).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import JSONResponse
    _HAVE_FASTAPI = True
except ImportError:            # OPTIONAL DEP — the file must still import
    FastAPI = None             # type: ignore[assignment]
    _HAVE_FASTAPI = False

from echo_config import CFG

log = logging.getLogger("echo.api")


# ── In-process registry (populated by the orchestrator) ────────
class _Registry:
    """Holds handles the API needs. Populated at bootstrap time."""

    def __init__(self) -> None:
        self.engine = None                       # CorrelationEngine
        self.orchestrator = None                 # EchoMulti
        self.lora = None                         # LoraSdrConnector
        self.lily_pads = None                    # LilyPadHub
        self.recent_events: deque = deque(maxlen=CFG["api"]["recent_events_cap"])
        self.recent_reports: deque = deque(maxlen=100)
        self.started_at = datetime.now(timezone.utc)
        self._lock = threading.RLock()

    def record_event(self, source: str, timestamp: datetime,
                     payload: dict) -> None:
        with self._lock:
            self.recent_events.append({
                "source": source,
                "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
                "payload": _jsonable(payload),
            })

    def record_report(self, report: Any) -> None:
        with self._lock:
            self.recent_reports.append(_report_to_dict(report))


REGISTRY = _Registry()


def _jsonable(v: Any) -> Any:
    """Coerce to JSON-safe for our loose payload dicts."""
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def _report_to_dict(report: Any) -> dict:
    """Minimal serialization of a CorrelationReport."""
    def _cand(c: Any) -> dict:
        return {
            "subject_type": c.subject_type,
            "subject_id": c.subject_id,
            "subject_name": c.subject_name,
            "score": c.score,
            "signals": c.signal_scores,
            "evidence": c.evidence,
        }
    return {
        "drone_event_id": report.drone_event_id,
        "drone_timestamp": report.drone_timestamp.astimezone(timezone.utc).isoformat(),
        "drone_camera": report.drone_camera,
        "drone_confidence": report.drone_confidence,
        "inmate_candidates": [_cand(c) for c in report.inmate_candidates],
        "external_candidates": [_cand(c) for c in report.external_candidates],
        "drone_signals": report.drone_signals,
        "drone_signal_evidence": report.drone_signal_evidence,
        "generated_at": report.generated_at.astimezone(timezone.utc).isoformat(),
    }


# ── FastAPI app ─────────────────────────────────────────────────
def _build_app() -> "FastAPI":
    if not _HAVE_FASTAPI:
        raise RuntimeError(
            "FastAPI is not installed. Install with: pip install 'fastapi[standard]' uvicorn"
        )
    app_ = FastAPI(
        title="ECHO API",
        version="1.0",
        docs_url="/docs" if CFG["api"].get("enable_docs", True) else None,
        redoc_url=None,
    )

    def _auth_guard(request: "Request") -> None:
        token = CFG["api"].get("bearer_token")
        if not token:
            # No token configured — only allow loopback origin
            client = (request.client.host if request.client else "") or ""
            if client not in ("127.0.0.1", "::1", "localhost"):
                raise HTTPException(
                    status_code=401,
                    detail="bearer_token not configured; non-loopback access refused",
                )
            return
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer ") or header[len("Bearer "):].strip() != token:
            raise HTTPException(status_code=401, detail="invalid bearer token")

    @app_.get("/health")
    def health() -> dict:
        return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}

    @app_.get("/status")
    def status(request: "Request") -> dict:
        _auth_guard(request)
        uptime_s = (datetime.now(timezone.utc) - REGISTRY.started_at).total_seconds()
        subs = _subsystem_health()
        return {
            "started_at": REGISTRY.started_at.isoformat(),
            "uptime_sec": int(uptime_s),
            "config": {
                "detector": CFG["detector"],
                "lora_enabled": CFG["lora"]["enabled"],
                "lily_pads_enabled": CFG["lily_pads"]["enabled"],
            },
            "counts": {
                "recent_events": len(REGISTRY.recent_events),
                "recent_reports": len(REGISTRY.recent_reports),
            },
            "subsystems": subs,
        }

    @app_.get("/detections")
    def detections(
        request: "Request",
        since: Optional[str] = Query(
            None,
            description="ISO8601 timestamp or unix seconds; return events strictly after this",
        ),
        limit: int = Query(200, ge=1, le=2000),
        source: Optional[str] = Query(
            None,
            description="Filter by source, e.g. drone_audio | lora_detection | face",
        ),
    ) -> dict:
        _auth_guard(request)
        cutoff = _parse_since(since)
        out = []
        for ev in REGISTRY.recent_events:
            if cutoff is not None:
                try:
                    ts = datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00"))
                except ValueError:
                    continue
                if ts <= cutoff:
                    continue
            if source and ev["source"] != source:
                continue
            out.append(ev)
        return {
            "count": len(out),
            "returned": min(len(out), limit),
            "events": out[-limit:],
        }

    @app_.post("/scan")
    def scan(request: "Request") -> dict:
        _auth_guard(request)
        if not CFG["api"].get("allow_scan_trigger", True):
            raise HTTPException(status_code=403, detail="scan trigger disabled in config")
        engine = REGISTRY.engine
        if engine is None:
            raise HTTPException(
                status_code=503,
                detail="no correlation engine attached; API running standalone",
            )
        # Fabricate a synthetic drone_audio event NOW and let the engine run
        from echo_correlation import Event                # local import to avoid cycle
        synthetic = Event(
            source="drone_audio",
            timestamp=datetime.now(),
            payload={
                "camera_id": "api_scan_trigger",
                "confidence": 0.0,
                "source_kind": "manual_scan",
            },
        )
        report = engine.correlate_drone(synthetic)
        return {"ok": True, "report": _report_to_dict(report)}

    @app_.get("/reports/recent")
    def recent_reports(request: "Request",
                       limit: int = Query(20, ge=1, le=100)) -> dict:
        _auth_guard(request)
        with REGISTRY._lock:
            reports = list(REGISTRY.recent_reports)[-limit:]
        return {"count": len(reports), "reports": reports}

    return app_


def _subsystem_health() -> dict:
    """Best-effort probe of each subsystem's aliveness."""
    out: dict = {}
    e = REGISTRY.engine
    out["correlation"] = {
        "attached": e is not None,
        "window_hours": CFG["correlation"]["window_hours"],
        "event_count": len(getattr(e, "_events", ())) if e is not None else 0,
    }
    orch = REGISTRY.orchestrator
    out["orchestrator"] = {
        "attached": orch is not None,
        "camera_count": len(getattr(orch, "runners", ())) if orch else 0,
    }
    out["lora"] = {
        "enabled": CFG["lora"]["enabled"],
        "attached": REGISTRY.lora is not None,
        "thread_alive": bool(getattr(REGISTRY.lora, "_thread", None)
                             and REGISTRY.lora._thread.is_alive())
                        if REGISTRY.lora is not None else False,
    }
    out["lily_pads"] = {
        "enabled": CFG["lily_pads"]["enabled"],
        "attached": REGISTRY.lily_pads is not None,
        "node_count": len(getattr(REGISTRY.lily_pads, "nodes", ())) if REGISTRY.lily_pads else 0,
    }
    return out


def _parse_since(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400,
                                detail="since= must be ISO8601 or unix seconds")


# ── Bootstrap ──────────────────────────────────────────────────
app = _build_app() if _HAVE_FASTAPI else None    # importable at module level


def maybe_start_api(engine=None, orchestrator=None,
                    lora=None, lily_pads=None) -> Optional[threading.Thread]:
    """
    Start the API in a background thread if CFG["api"]["enabled"] and
    FastAPI + uvicorn are installed. Wires up the registry so /status
    reflects the running pipeline.

    Returns the server thread (daemon) or None if disabled/unavailable.
    """
    if not CFG["api"]["enabled"]:
        log.info("API disabled in config (api.enabled=false)")
        return None
    if not _HAVE_FASTAPI:
        log.warning("api.enabled=true but FastAPI not installed — skipping")
        return None
    try:
        import uvicorn
    except ImportError:
        log.warning("uvicorn not installed — cannot start API server")
        return None

    host = CFG["api"]["host"]
    port = CFG["api"]["port"]
    token = CFG["api"].get("bearer_token")
    if host not in ("127.0.0.1", "localhost", "::1") and not token:
        raise RuntimeError(
            f"api.host={host!r} exposes the service beyond loopback, "
            "but api.bearer_token is unset. Refusing to start."
        )

    REGISTRY.engine = engine
    REGISTRY.orchestrator = orchestrator
    REGISTRY.lora = lora
    REGISTRY.lily_pads = lily_pads

    # Also wrap engine.ingest to record events into the API's ring buffer.
    if engine is not None:
        _wire_event_recording(engine)

    def _run() -> None:
        uvicorn.run(app, host=host, port=port, log_level=CFG["logging"]["level"].lower())

    t = threading.Thread(target=_run, name="echo-api", daemon=True)
    t.start()
    log.info("ECHO API started on %s:%d (docs at /docs)", host, port)
    return t


def _wire_event_recording(engine) -> None:
    """Monkey-hook engine.ingest so each event lands in REGISTRY too."""
    orig_ingest = engine.ingest
    orig_on_report = engine.on_report

    def _ingest(event) -> None:
        REGISTRY.record_event(event.source, event.timestamp, event.payload)
        return orig_ingest(event)

    def _on_report(report) -> None:
        REGISTRY.record_report(report)
        if orig_on_report:
            orig_on_report(report)

    engine.ingest = _ingest
    engine.on_report = _on_report


if __name__ == "__main__":
    # Standalone dev run (no attached engine — API returns 503 for /scan
    # and reports zero attached subsystems).
    logging.basicConfig(
        level=CFG["logging"]["level"],
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    if not _HAVE_FASTAPI:
        raise SystemExit("FastAPI not installed. `pip install fastapi uvicorn`")
    import uvicorn
    uvicorn.run(app,
                host=CFG["api"]["host"] or "127.0.0.1",
                port=int(CFG["api"]["port"] or 5058),
                log_level=CFG["logging"]["level"].lower())
