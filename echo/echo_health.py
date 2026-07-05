"""
ECHO subsystem health registry + fault-isolation loop wrapper.

Every subsystem in ECHO — cameras, LoRa SDR, Lily Pad hub, vendor
connectors (ViaPath, Tecore, Dedrone, Flock, DMV, Cellebrite),
forensics watcher, face recognizer — should:

  1. Report its health status here (OK / DEGRADED / DOWN / UNKNOWN).
  2. Run its main loop inside `safe_loop()` so an uncaught exception
     stops THAT subsystem's loop instead of taking down the pipeline.

The fusion layer (CORTEX = `echo_correlation.CorrelationEngine`) reads
this registry when scoring, drops signals from DOWN subsystems, and
declines to decide at all if too few subsystems are alive.

Design principle: **fail loud into the registry, silent to the pipeline**.
A camera going down should light up the operator dashboard, but the
audio pipeline for the other cameras should keep running unaffected.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

log = logging.getLogger("echo.health")


class HealthStatus(str, Enum):
    """Standard three-tier status plus UNKNOWN for not-yet-reported."""
    OK        = "OK"          # producing valid data, no recent errors
    DEGRADED  = "DEGRADED"    # producing data but with warnings / retries / partial coverage
    DOWN      = "DOWN"        # not producing data — errors, disconnected, crashed loop
    UNKNOWN   = "UNKNOWN"     # never reported (subsystem not enabled or not started)


# Which HealthStatus values still contribute signals to fusion (in weight order)
FUSION_WEIGHT_MULTIPLIER = {
    HealthStatus.OK:       1.0,
    HealthStatus.DEGRADED: 0.5,   # weighted-half — signal is present but may be flakey
    HealthStatus.DOWN:     0.0,   # dropped
    HealthStatus.UNKNOWN:  0.0,   # dropped (never came up = not producing signals anyway)
}


@dataclass
class SubsystemHealth:
    """One subsystem's health record."""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_ok_at: Optional[datetime] = None
    last_change_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    error_count: int = 0
    ok_count: int = 0
    detail: dict = field(default_factory=dict)     # subsystem-specific metadata

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "last_ok_at": self.last_ok_at.isoformat() if self.last_ok_at else None,
            "last_change_at": self.last_change_at.isoformat(),
            "last_error": self.last_error,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "error_count": self.error_count,
            "ok_count": self.ok_count,
            "detail": self.detail,
        }


class HealthRegistry:
    """
    Thread-safe registry of subsystem health.

    Every subsystem registers itself once at start-up and then reports
    ticks via `report_ok()`, `report_degraded()`, `report_down()`. The
    registry auto-demotes to DOWN if a subsystem stops reporting for
    longer than its stale-timeout.
    """

    def __init__(self, stale_timeout_sec: float = 60.0) -> None:
        self.stale_timeout_sec = stale_timeout_sec
        self._registry: dict[str, SubsystemHealth] = {}
        self._listeners: list[Callable[[SubsystemHealth, HealthStatus], None]] = []
        self._lock = threading.RLock()

    # ── Registration ──────────────────────────────────────
    def register(self, name: str, **detail) -> SubsystemHealth:
        with self._lock:
            if name not in self._registry:
                self._registry[name] = SubsystemHealth(name=name, detail=detail)
                log.info("subsystem registered: %s (%s)",
                         name, ", ".join(f"{k}={v}" for k, v in detail.items()))
            else:
                self._registry[name].detail.update(detail)
            return self._registry[name]

    def unregister(self, name: str) -> None:
        with self._lock:
            self._registry.pop(name, None)

    # ── Reporting ─────────────────────────────────────────
    def report_ok(self, name: str, **detail) -> None:
        self._transition(name, HealthStatus.OK, None, detail)

    def report_degraded(self, name: str, reason: str, **detail) -> None:
        self._transition(name, HealthStatus.DEGRADED, reason, detail)

    def report_down(self, name: str, reason: str, **detail) -> None:
        self._transition(name, HealthStatus.DOWN, reason, detail)

    def _transition(self, name: str, status: HealthStatus,
                    reason: Optional[str], detail: dict) -> None:
        with self._lock:
            h = self._registry.get(name) or self.register(name)
            prev = h.status
            now = datetime.now(timezone.utc)
            if status is HealthStatus.OK:
                h.last_ok_at = now
                h.ok_count += 1
            else:
                h.last_error = reason
                h.last_error_at = now
                h.error_count += 1
            if prev is not status:
                h.status = status
                h.last_change_at = now
                log.info("health: %s %s → %s (%s)", name, prev.value, status.value, reason or "")
                self._fire(h, prev)
            if detail:
                h.detail.update(detail)

    def on_change(self, cb: Callable[[SubsystemHealth, HealthStatus], None]) -> None:
        """Register a callback fired when a subsystem's status changes."""
        with self._lock:
            self._listeners.append(cb)

    def _fire(self, h: SubsystemHealth, prev: HealthStatus) -> None:
        for cb in list(self._listeners):
            try:
                cb(h, prev)
            except Exception:
                log.exception("health listener failed")

    # ── Query ─────────────────────────────────────────────
    def snapshot(self) -> dict[str, dict]:
        self._sweep_stale()
        with self._lock:
            return {n: h.as_dict() for n, h in self._registry.items()}

    def get(self, name: str) -> Optional[SubsystemHealth]:
        self._sweep_stale()
        with self._lock:
            return self._registry.get(name)

    def status_of(self, name: str) -> HealthStatus:
        h = self.get(name)
        return h.status if h else HealthStatus.UNKNOWN

    def is_up(self, name: str) -> bool:
        """OK or DEGRADED counts as up — data is still flowing."""
        return self.status_of(name) in (HealthStatus.OK, HealthStatus.DEGRADED)

    def count_by_status(self) -> dict[HealthStatus, int]:
        self._sweep_stale()
        with self._lock:
            out = {s: 0 for s in HealthStatus}
            for h in self._registry.values():
                out[h.status] += 1
        return out

    def fusion_weight(self, name: str) -> float:
        """Multiplier for a signal from this subsystem (1.0 / 0.5 / 0.0)."""
        return FUSION_WEIGHT_MULTIPLIER[self.status_of(name)]

    def _sweep_stale(self) -> None:
        """Auto-demote to DOWN any subsystem that stopped reporting."""
        now = datetime.now(timezone.utc)
        with self._lock:
            for h in self._registry.values():
                if h.status is HealthStatus.DOWN or h.status is HealthStatus.UNKNOWN:
                    continue
                anchor = h.last_ok_at or h.last_change_at
                age = (now - anchor).total_seconds()
                if age > self.stale_timeout_sec:
                    prev = h.status
                    h.status = HealthStatus.DOWN
                    h.last_change_at = now
                    h.last_error = f"no report for {age:.0f}s (stale timeout {self.stale_timeout_sec:.0f}s)"
                    h.last_error_at = now
                    h.error_count += 1
                    log.warning("health: %s auto-demoted %s → DOWN (%s)",
                                h.name, prev.value, h.last_error)
                    self._fire(h, prev)


# ── Module-level singleton ─────────────────────────────────────
REGISTRY = HealthRegistry()


# ── safe_loop: isolated exception handling for subsystem threads ──
def safe_loop(
    subsystem: str,
    body: Callable[[], None],
    *,
    stop_event: Optional[threading.Event] = None,
    tick_sec: float = 1.0,
    max_consecutive_errors: int = 10,
    backoff_sec: float = 5.0,
    on_ok: bool = True,
) -> None:
    """
    Run `body()` repeatedly with isolated exception handling.

    - Reports OK after each successful tick (if `on_ok=True`).
    - Reports DEGRADED after 3 consecutive errors, DOWN after
      `max_consecutive_errors` — but continues trying with exponential
      backoff instead of raising.
    - Never lets an exception escape this function. The worst case is
      the subsystem sitting in DOWN state, retrying every `backoff_sec`
      seconds until the operator fixes it.

    Wire example (inside a subsystem's start()):

        threading.Thread(
            target=lambda: safe_loop(
                "camera:cam-yard-east",
                self._one_iteration,
                stop_event=self._stop,
                tick_sec=0.1,
            ),
            daemon=True,
            name="cam-yard-east",
        ).start()
    """
    REGISTRY.register(subsystem)
    consec_errors = 0
    while stop_event is None or not stop_event.is_set():
        try:
            body()
            if on_ok:
                REGISTRY.report_ok(subsystem)
            consec_errors = 0
        except Exception as exc:
            consec_errors += 1
            reason = f"{type(exc).__name__}: {exc}"
            tb = traceback.format_exc(limit=2)
            log.error("[%s] loop error #%d: %s\n%s", subsystem, consec_errors, reason, tb)
            if consec_errors >= max_consecutive_errors:
                REGISTRY.report_down(subsystem, reason)
                _sleep_with_stop(backoff_sec * min(consec_errors / max_consecutive_errors, 4.0),
                                 stop_event)
                continue
            if consec_errors >= 3:
                REGISTRY.report_degraded(subsystem, reason)
            _sleep_with_stop(backoff_sec, stop_event)
            continue
        _sleep_with_stop(tick_sec, stop_event)
    REGISTRY.report_down(subsystem, "loop exited (stop event)")


def _sleep_with_stop(seconds: float,
                     stop_event: Optional[threading.Event]) -> None:
    if stop_event is None:
        time.sleep(seconds)
        return
    stop_event.wait(seconds)


# ── Convenience context manager for one-shot ops ────────────────
class report_health:                    # snake_case: used like a decorator/context
    """
    Context manager that reports OK on clean exit, DOWN on exception.

    Use when a subsystem isn't a loop but a single operation whose
    success/failure we still want tracked:

        with report_health("dmv:sc"):
            plate = sc_dmv.lookup(plate_number)   # if this raises → DOWN
    """
    def __init__(self, subsystem: str, on_ok: bool = True) -> None:
        self.subsystem = subsystem
        self.on_ok = on_ok

    def __enter__(self) -> None:
        REGISTRY.register(self.subsystem)

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            if self.on_ok:
                REGISTRY.report_ok(self.subsystem)
            return False
        reason = f"{exc_type.__name__}: {exc}"
        REGISTRY.report_down(self.subsystem, reason)
        return False       # don't swallow


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    # Toy demo
    REGISTRY.register("cam-yard-east", role="camera", url="rtsp://...")
    REGISTRY.report_ok("cam-yard-east")
    REGISTRY.register("dedrone", role="counter_uas")
    REGISTRY.report_degraded("dedrone", "polling latency high")
    REGISTRY.report_down("lora-sdr", "USB device disconnected")
    import json
    print(json.dumps(REGISTRY.snapshot(), indent=2, default=str))
    print("counts:", {k.value: v for k, v in REGISTRY.count_by_status().items()})
    print("fusion weight, cam-yard-east:", REGISTRY.fusion_weight("cam-yard-east"))
    print("fusion weight, dedrone:", REGISTRY.fusion_weight("dedrone"))
    print("fusion weight, lora-sdr:", REGISTRY.fusion_weight("lora-sdr"))
