"""
ECHO pipeline state machine.

Explicit lifecycle for every ECHO instance:

    ┌────────┐  drone signal ≥ floor    ┌───────────┐
    │  IDLE  │────────────────────────▶│  SCANNING │
    └────────┘                         └───────────┘
        ▲                                 │      ▲
        │ scan_timeout / no signal        │      │ signal fades
        │                                 ▼      │
        │                             ┌──────────┴──┐
        │                             │  TRACKING   │
        │                             └──────────┬──┘
        │                                        │ correlation report ≥ ALERT floor
        │                                        ▼
        │                                    ┌───────┐
        └────────────────── ack ─────────────┤ ALERT │
                                             └───────┘

States:
    IDLE      no signals; detector loops running but nothing above floor
    SCANNING  a candidate signal is being investigated (audio harmonic
              stack hit, single vision detection, single LoRa chirp)
    TRACKING  confirmed drone — building up multi-source evidence
    ALERT     correlation report reached an alert-worthy score; SIU
              paged, dashboard blinking. Stays ALERT until acked or
              the underlying signals drop for the ack-timeout.

Every transition logs (timestamp, from → to, trigger reason, event id).
Invalid transitions raise `InvalidTransition` — the caller decides
whether to swallow or escalate.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

log = logging.getLogger("echo.state")


class PipelineState(str, Enum):
    IDLE     = "IDLE"
    SCANNING = "SCANNING"
    TRACKING = "TRACKING"
    ALERT    = "ALERT"


# Transition table.  Every legal from-state → set of to-states.
# Anything not listed here is invalid and raises InvalidTransition.
TRANSITIONS: dict[PipelineState, set[PipelineState]] = {
    PipelineState.IDLE:     {PipelineState.SCANNING},
    PipelineState.SCANNING: {PipelineState.IDLE, PipelineState.TRACKING, PipelineState.ALERT},
    PipelineState.TRACKING: {PipelineState.SCANNING, PipelineState.ALERT},
    PipelineState.ALERT:    {PipelineState.TRACKING, PipelineState.SCANNING, PipelineState.IDLE},
}

# Trigger vocabulary — free-form strings but keep it tight so log
# analysis stays sane. See `Trigger` below for the canonical ones.
class Trigger:
    SIGNAL_ABOVE_FLOOR    = "signal_above_floor"
    SIGNAL_BELOW_FLOOR    = "signal_below_floor"
    SIGNAL_CONFIRMED      = "signal_confirmed"
    SIGNAL_FADED          = "signal_faded"
    CORRELATION_REPORT    = "correlation_report"
    ALERT_ACKED           = "alert_acked"
    ALERT_TIMEOUT         = "alert_timeout"
    SCAN_TIMEOUT          = "scan_timeout"
    OPERATOR_MANUAL       = "operator_manual"


class InvalidTransition(RuntimeError):
    def __init__(self, current: PipelineState, requested: PipelineState) -> None:
        super().__init__(
            f"invalid transition {current.value} → {requested.value}; "
            f"allowed from {current.value}: "
            f"{sorted(s.value for s in TRANSITIONS.get(current, set()))}"
        )
        self.current = current
        self.requested = requested


@dataclass
class TransitionRecord:
    ts: datetime
    from_state: PipelineState
    to_state: PipelineState
    trigger: str
    event_id: Optional[str] = None
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "ts": self.ts.isoformat(),
            "from": self.from_state.value,
            "to": self.to_state.value,
            "trigger": self.trigger,
            "event_id": self.event_id,
            "detail": self.detail,
        }


class PipelineStateMachine:
    """
    Explicit, guarded, logged, thread-safe pipeline state machine.

    Usage:

        sm = PipelineStateMachine()

        # In the detector, when audio harmonic stack hits:
        if sm.state is PipelineState.IDLE:
            sm.transition(PipelineState.SCANNING,
                          trigger=Trigger.SIGNAL_ABOVE_FLOOR,
                          event_id=str(id(event)))

        # In the correlator, when it produces a report ≥ alert score:
        sm.transition(PipelineState.ALERT,
                      trigger=Trigger.CORRELATION_REPORT,
                      detail={"top_inmate": ...})

    Guards:
        - Invalid transitions raise InvalidTransition (unless
          allow_invalid=True is passed at construction).
        - Re-entering the same state is a NO-OP; not an error.
        - A `history_cap` bounded ring buffer keeps the last N
          transitions for `/state/history` in the API.
    """

    def __init__(self,
                 initial: PipelineState = PipelineState.IDLE,
                 allow_invalid: bool = False,
                 history_cap: int = 256,
                 on_transition: Optional[Callable[[TransitionRecord], None]] = None) -> None:
        self._state = initial
        self._allow_invalid = allow_invalid
        self._history: list[TransitionRecord] = []
        self._history_cap = history_cap
        self._lock = threading.RLock()
        self._listeners: list[Callable[[TransitionRecord], None]] = []
        self._entered_at = datetime.now(timezone.utc)
        if on_transition:
            self._listeners.append(on_transition)

    # ── Query ─────────────────────────────────────────────
    @property
    def state(self) -> PipelineState:
        with self._lock:
            return self._state

    @property
    def uptime_in_state_sec(self) -> float:
        return (datetime.now(timezone.utc) - self._entered_at).total_seconds()

    def history(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return [r.as_dict() for r in self._history[-limit:]]

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self._state.value,
                "entered_at": self._entered_at.isoformat(),
                "uptime_in_state_sec": self.uptime_in_state_sec,
                "allowed_next": sorted(
                    s.value for s in TRANSITIONS.get(self._state, set())
                ),
                "history_len": len(self._history),
            }

    # ── Mutate ────────────────────────────────────────────
    def transition(self,
                   to: PipelineState,
                   *,
                   trigger: str,
                   event_id: Optional[str] = None,
                   detail: Optional[dict] = None) -> TransitionRecord:
        """
        Move to `to`. Raises InvalidTransition unless (a) it's a legal
        move per TRANSITIONS or (b) allow_invalid=True was set.

        A same-state transition is a no-op that still logs the trigger
        (useful for "still tracking, new evidence arrived" heartbeats).
        """
        with self._lock:
            frm = self._state
            if to is frm:
                rec = TransitionRecord(
                    ts=datetime.now(timezone.utc),
                    from_state=frm,
                    to_state=to,
                    trigger=trigger,
                    event_id=event_id,
                    detail=detail or {"note": "same-state heartbeat"},
                )
                self._record(rec, log_level=logging.DEBUG)
                return rec
            legal = TRANSITIONS.get(frm, set())
            if to not in legal and not self._allow_invalid:
                raise InvalidTransition(frm, to)
            rec = TransitionRecord(
                ts=datetime.now(timezone.utc),
                from_state=frm,
                to_state=to,
                trigger=trigger,
                event_id=event_id,
                detail=detail or {},
            )
            self._state = to
            self._entered_at = rec.ts
            self._record(rec, log_level=logging.INFO)
            return rec

    def try_transition(self,
                       to: PipelineState,
                       *,
                       trigger: str,
                       event_id: Optional[str] = None,
                       detail: Optional[dict] = None) -> Optional[TransitionRecord]:
        """Non-raising variant. Returns None on invalid transition."""
        try:
            return self.transition(to, trigger=trigger,
                                   event_id=event_id, detail=detail)
        except InvalidTransition as e:
            log.debug("blocked transition: %s", e)
            return None

    # ── Listeners ─────────────────────────────────────────
    def on_transition(self, cb: Callable[[TransitionRecord], None]) -> None:
        with self._lock:
            self._listeners.append(cb)

    def _record(self, rec: TransitionRecord, log_level: int) -> None:
        self._history.append(rec)
        if len(self._history) > self._history_cap:
            self._history = self._history[-self._history_cap:]
        log.log(log_level,
                "state: %s → %s  trigger=%s  event=%s  detail=%s",
                rec.from_state.value, rec.to_state.value, rec.trigger,
                rec.event_id, rec.detail)
        for cb in list(self._listeners):
            try:
                cb(rec)
            except Exception:
                log.exception("state listener failed")


# ── Convenience: hooks for wiring into the pipeline ───────────
def bind_to_correlation_engine(sm: PipelineStateMachine, engine,
                               alert_score_floor: float = 0.5) -> None:
    """
    Auto-transition based on correlation engine activity:

    - engine.ingest(drone_audio | drone_visual)
      → IDLE → SCANNING → TRACKING (via wrapped ingest)

    - correlation report with top-candidate score ≥ alert_score_floor
      → TRACKING → ALERT
    """
    orig_ingest = engine.ingest
    orig_on_report = engine.on_report

    def _ingest(event) -> None:
        if event.source in ("drone_audio", "drone_visual"):
            if sm.state is PipelineState.IDLE:
                sm.try_transition(PipelineState.SCANNING,
                                  trigger=Trigger.SIGNAL_ABOVE_FLOOR,
                                  event_id=str(id(event)),
                                  detail={"source": event.source,
                                          "confidence": event.payload.get("confidence")})
            elif sm.state is PipelineState.SCANNING:
                sm.try_transition(PipelineState.TRACKING,
                                  trigger=Trigger.SIGNAL_CONFIRMED,
                                  event_id=str(id(event)),
                                  detail={"source": event.source})
        return orig_ingest(event)

    def _on_report(report) -> None:
        # L4 fix: never assume report shape. A future declined-report or
        # partial shape must not AttributeError inside a listener callback
        # (that would kill state-machine advancement AND leak the
        # exception into the correlation engine's own on_report call).
        inmates = getattr(report, "inmate_candidates", None) or []
        externals = getattr(report, "external_candidates", None) or []
        top = max(
            (c.score for c in (inmates + externals) if hasattr(c, "score")),
            default=0.0,
        )
        if top >= alert_score_floor and sm.state in (PipelineState.TRACKING, PipelineState.SCANNING):
            sm.try_transition(PipelineState.ALERT,
                              trigger=Trigger.CORRELATION_REPORT,
                              event_id=getattr(report, "drone_event_id", None),
                              detail={"top_score": round(top, 3)})
        if orig_on_report:
            orig_on_report(report)

    engine.ingest = _ingest
    engine.on_report = _on_report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    sm = PipelineStateMachine()
    print("start:", sm.snapshot())
    sm.transition(PipelineState.SCANNING, trigger=Trigger.SIGNAL_ABOVE_FLOOR)
    sm.transition(PipelineState.TRACKING, trigger=Trigger.SIGNAL_CONFIRMED)
    sm.transition(PipelineState.ALERT,    trigger=Trigger.CORRELATION_REPORT,
                  detail={"top_score": 0.71})
    try:
        # ALERT → SCANNING is legal (after ack); ALERT → TRACKING legal;
        # ALERT → IDLE legal. Let's test an invalid: IDLE → TRACKING.
        sm2 = PipelineStateMachine()
        sm2.transition(PipelineState.TRACKING, trigger="test")
    except InvalidTransition as e:
        print("caught expected:", e)
    sm.transition(PipelineState.SCANNING, trigger=Trigger.ALERT_ACKED)
    print("end:", sm.snapshot())
    print("history:")
    for r in sm.history():
        print(" ", r)
