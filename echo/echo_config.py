"""
ECHO config loader.

Single source of truth for every tunable. Load order (later overrides):

    1. Baked defaults in DEFAULTS below
    2. config.yaml (path = ECHO_CONFIG env var, else ./echo/config.yaml)
    3. ECHO_* environment variables
    4. Per-run overrides passed at load() time

Usage:

    from echo_config import CFG            # loads on first import
    threshold = CFG["detector"]["min_level_db"]

    # or explicitly reload with a specific file:
    from echo_config import load
    cfg = load("path/to/config.yaml")

    # env override examples:
    ECHO_DETECTOR__MIN_LEVEL_DB=-42 python echo_multi.py --config ...

The double-underscore in env var names indicates nesting:
`ECHO_DETECTOR__MIN_LEVEL_DB` → cfg["detector"]["min_level_db"].
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml  # PyYAML is already in requirements.txt

log = logging.getLogger("echo.config")


# ── Baked defaults (mirror config.yaml for headless / no-file starts)
DEFAULTS: dict = {
    "detector": {
        "sample_rate_hz": 44100,
        "block_samples": 16384,
        "harmonics": [1, 2, 3, 4, 5, 6],
        "harmonic_snr_db": 8.0,
        "mains_hz": 60,
        "mains_width_hz": 5,
        "min_level_db": -45.0,
        "max_drift_hz": 6.0,
        "min_continuity": 0.85,
        "min_harmonics": 2,
        "persist_sec": 2.0,
        "ml_confidence_floor": 0.55,
    },
    "multi": {
        "cameras_yaml_path": "echo/echo_cameras.yaml",
        "reload_seconds": 0,
        "face_source": "placeholder",
    },
    "correlation": {
        "window_hours": 4,
        "top_n_report": 10,
        "min_viable_sensors": 2,
        "alert_score_floor": 0.5,
        "weights": {},        # empty → use DEFAULT_WEIGHTS from echo_correlation.py
    },
    "health": {
        "stale_timeout_sec": 60,
        "safe_loop_max_consecutive_errors": 10,
        "safe_loop_backoff_sec": 5.0,
    },
    "state_machine": {
        "alert_auto_ack_sec": 0,
        "history_cap": 256,
    },
    "lora": {
        "enabled": False,
        "region": "US915",
        "device": "rtlsdr",
        "device_index": 0,
        "sample_rate_sps": 2_400_000,
        "gain_db": 40.0,
        "min_rssi_dbm": -105.0,
        "sweep_dwell_sec": 2.0,
        "facility_whitelist_hz": [],
        "correlation_window_sec": 90,
    },
    "lily_pads": {
        "enabled": False,
        "tdoa_group_window_ms": 800,
        "min_nodes_for_fix": 3,
        "speed_of_sound_mps": 343.0,
        "clock_sync_error_penalty_ms": 5,
        "geo_anchor_lat": None,
        "geo_anchor_lng": None,
        "geo_anchor_bearing_deg": 0.0,
        "nodes": [],
        "net_pole_array": {
            "enabled": False,
            "site_id": "facility-01",
            "pole_spacing_m": 9.0,
            "pole_height_m": 12.0,
            "outward_facing": True,
            "windscreen": True,
            "vibration_isolated": True,
            "perimeter_polygon_m": [],
        },
    },
    "api": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 5058,
        "bearer_token": None,
        "recent_events_cap": 500,
        "allow_scan_trigger": True,
    },
    "paths": {
        "log_dir": "echo/logs",
        "ml_model_path": "echo/echo_drone_clf.joblib",
        "iq_capture_dir": "echo/logs/lora_iq",
        "iq_retention_hours": 24,
    },
    "logging": {
        "level": "INFO",
        "console": True,
        "file": "echo/logs/echo.log",
        "rotate_max_bytes": 10 * 1024 * 1024,
        "rotate_backup_count": 5,
    },
}


def _default_config_path() -> Path:
    """Look for config.yaml next to this file first, then ECHO_CONFIG env, then cwd."""
    envp = os.environ.get("ECHO_CONFIG")
    if envp:
        return Path(envp)
    here = Path(__file__).with_name("config.yaml")
    if here.exists():
        return here
    return Path("echo/config.yaml")


def _deep_merge(base: dict, over: dict) -> dict:
    """Recursively merge `over` into `base`, without mutating either."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _apply_env_overrides(cfg: dict) -> dict:
    """
    Convert ECHO_SECTION__KEY=value env vars into nested dict overrides.

    Type coercion order: JSON (for lists/dicts/numbers/booleans/null),
    then bool literals, then int, then float, then string.

    H5 safety: if the target key exists in the base cfg as a list or
    dict, refuse to coerce a bare comma-separated string to it — the
    old behavior silently assigned "1,2,3" to detector.harmonics as
    a raw string, then the detector iterated characters. Now we
    require JSON for list/dict overrides and log an error otherwise.
    """
    overrides: dict = {}
    rejected: list[str] = []
    for name, val in os.environ.items():
        if not name.startswith("ECHO_"):
            continue
        parts = name[len("ECHO_"):].split("__")
        if len(parts) < 2:
            continue
        parts = [p.lower() for p in parts]

        # Look up the target key's existing type in cfg (if any)
        target_kind: Optional[type] = None
        cursor_cfg: Any = cfg
        for p in parts:
            if isinstance(cursor_cfg, dict) and p in cursor_cfg:
                cursor_cfg = cursor_cfg[p]
            else:
                cursor_cfg = None
                break
        if cursor_cfg is not None:
            target_kind = type(cursor_cfg)

        # Re-review #6: only attempt JSON parsing when the target field
        # is a list or dict. Otherwise a legitimate string value like
        # `ECHO_LOGGING__FORMAT='[%(asctime)s]'` would trigger a
        # JSONDecodeError attempt on every startup, and (more subtly) a
        # user who typo'd a JSON list on a scalar field would get the
        # string silently kept without a diagnostic.
        try_json = target_kind in (list, dict)
        coerced = _coerce(val, try_json=try_json)

        # Guard: don't allow a bare string to overwrite a list/dict.
        if target_kind in (list, dict) and not isinstance(coerced, (list, dict)):
            rejected.append(
                f"{name}: target is {target_kind.__name__}, but value "
                f"{val!r} did not parse as JSON. To override, set "
                f'{name}=\'[1,2,3]\' (JSON syntax).'
            )
            continue

        cursor = overrides
        for p in parts[:-1]:
            cursor = cursor.setdefault(p, {})
        cursor[parts[-1]] = coerced

    for msg in rejected:
        log.error("REJECTED env override — %s", msg)
    if overrides:
        log.debug("ECHO_ env overrides: %s", overrides)
        return _deep_merge(cfg, overrides)
    return cfg


def _coerce(v: str, try_json: bool = False) -> Any:
    """Coerce an env-var string to a Python value.

    JSON parsing is attempted only when `try_json=True` — i.e. when the
    caller knows the target field is a list or dict. That keeps innocent
    string values with leading brackets (log format strings, regexes)
    from tripping a spurious JSON decode.
    """
    stripped = v.strip()
    if try_json and stripped and stripped[0] in "[{":
        try:
            return json.loads(stripped)
        except (ValueError, json.JSONDecodeError):
            pass
    low = stripped.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", ""):
        return None
    try:
        if "." in v or "e" in low:
            return float(v)
        return int(v)
    except ValueError:
        return v


def load(path: Optional[str] = None,
         overrides: Optional[dict] = None) -> dict:
    """
    Load configuration. Returns a fresh dict — callers get their own copy.

    Args:
        path:      explicit path to config.yaml; None = auto-discover
        overrides: highest-precedence per-run overrides

    Missing file is not an error — defaults are returned.
    """
    cfg = copy.deepcopy(DEFAULTS)
    fpath = Path(path) if path else _default_config_path()
    if fpath.exists():
        try:
            with fpath.open() as f:
                loaded = yaml.safe_load(f) or {}
            cfg = _deep_merge(cfg, loaded)
            log.info("loaded config from %s", fpath)
        except Exception:
            log.exception("failed to parse %s — using baked defaults", fpath)
    else:
        log.info("no config.yaml at %s — using baked defaults", fpath)
    cfg = _apply_env_overrides(cfg)
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    return cfg


# Module-level default instance for the common `from echo_config import CFG` case
CFG: dict = load()


if __name__ == "__main__":
    import json
    print(json.dumps(CFG, indent=2, default=str))
