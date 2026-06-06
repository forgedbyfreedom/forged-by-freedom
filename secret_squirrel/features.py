"""Acoustic feature extraction for voice stress analysis.

Uses Parselmouth (Praat wrapper) for the gold-standard implementations of
F0, jitter, shimmer, HNR, and intensity. These are the same features used in
peer-reviewed stress/cognitive-load research (see PMC12289014 systematic review).
"""
from __future__ import annotations

import numpy as np
import parselmouth
from parselmouth.praat import call


def _safe_call(*args, **kwargs):
    try:
        v = call(*args, **kwargs)
        if v is None:
            return None
        v = float(v)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    except Exception:
        return None


def extract_features(audio: np.ndarray, fs: int,
                     f0min: float = 75.0, f0max: float = 500.0) -> dict:
    """Extract per-utterance acoustic features.

    Returns a dict with these keys (values may be None when undefined):
      f0_mean, f0_std       — pitch and pitch variability (Hz)
      jitter_local          — cycle-to-cycle pitch period perturbation
      shimmer_local         — cycle-to-cycle amplitude perturbation
      hnr                   — harmonics-to-noise ratio (dB)
      intensity_mean        — loudness (dB)
      intensity_std         — loudness variability
      speaking_rate         — voiced-segment onsets per second
      pause_ratio           — fraction of utterance with no voicing
    """
    if audio.size == 0:
        return {}
    if audio.dtype != np.float64:
        audio = audio.astype(np.float64)

    sound = parselmouth.Sound(values=audio, sampling_frequency=fs)
    total_sec = audio.size / fs

    # ── Pitch (F0) ──────────────────────────────────────────────────
    try:
        pitch = sound.to_pitch_ac(time_step=0.01,
                                  pitch_floor=f0min,
                                  pitch_ceiling=f0max)
        f0 = pitch.selected_array["frequency"]
    except Exception:
        f0 = np.array([])

    voiced = f0[f0 > 0]
    f0_mean = float(np.mean(voiced)) if voiced.size else None
    f0_std = float(np.std(voiced)) if voiced.size > 1 else None

    # ── Jitter / Shimmer via PointProcess ───────────────────────────
    try:
        pp = call(sound, "To PointProcess (periodic, cc)", f0min, f0max)
        jitter_local = _safe_call(pp, "Get jitter (local)",
                                  0, 0, 0.0001, 0.02, 1.3)
        shimmer_local = _safe_call([sound, pp], "Get shimmer (local)",
                                   0, 0, 0.0001, 0.02, 1.3, 1.6)
    except Exception:
        jitter_local = None
        shimmer_local = None

    # ── HNR ─────────────────────────────────────────────────────────
    try:
        harm = sound.to_harmonicity_cc(time_step=0.01,
                                       minimum_pitch=f0min,
                                       silence_threshold=0.1,
                                       periods_per_window=1.0)
        hnr_vals = harm.values[harm.values > -200]
        hnr = float(np.mean(hnr_vals)) if hnr_vals.size else None
    except Exception:
        hnr = None

    # ── Intensity ───────────────────────────────────────────────────
    try:
        intens = sound.to_intensity(time_step=0.01)
        ivals = intens.values[0]
        ivalid = ivals[ivals > 0]
        intensity_mean = float(np.mean(ivalid)) if ivalid.size else None
        intensity_std = float(np.std(ivalid)) if ivalid.size > 1 else None
    except Exception:
        intensity_mean = None
        intensity_std = None

    # ── Speaking rate (proxy: voiced-onset count / sec) ─────────────
    speaking_rate = None
    pause_ratio = None
    if f0.size and total_sec > 0:
        voiced_mask = (f0 > 0).astype(np.int8)
        onsets = int(np.sum(np.diff(voiced_mask) == 1))
        speaking_rate = float(onsets / max(total_sec, 1e-6))
        voiced_sec = voiced.size * 0.01
        pause_ratio = float(max(0.0, 1.0 - voiced_sec / total_sec))

    return {
        "f0_mean": f0_mean,
        "f0_std": f0_std,
        "jitter_local": jitter_local,
        "shimmer_local": shimmer_local,
        "hnr": hnr,
        "intensity_mean": intensity_mean,
        "intensity_std": intensity_std,
        "speaking_rate": speaking_rate,
        "pause_ratio": pause_ratio,
        "duration_sec": float(total_sec),
    }
