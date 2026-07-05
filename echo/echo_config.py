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
        "weights": {},        # empty → use DEFAULT_WEIGHTS from echo_correlation.py
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

    Type coercion is attempted in this order: bool, int, float, str.
    A value of `null` (or `none`) becomes Python None.
    """
    overrides: dict = {}
    for name, val in os.environ.items():
        if not name.startswith("ECHO_"):
            continue
        # Ignore known non-config-nested prefixes used by echo_engine.py
        # (they map to the flat detector.* section already covered below).
        parts = name[len("ECHO_"):].split("__")
        if len(parts) < 2:
            continue
        parts = [p.lower() for p in parts]
        cursor = overrides
        for p in parts[:-1]:
            cursor = cursor.setdefault(p, {})
        cursor[parts[-1]] = _coerce(val)
    if overrides:
        log.debug("ECHO_ env overrides: %s", overrides)
        return _deep_merge(cfg, overrides)
    return cfg


def _coerce(v: str) -> Any:
    low = v.strip().lower()
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
