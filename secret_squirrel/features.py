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

    # ── Prosody trajectory ─────────────────────────────────────────
    f0_iqr = None
    f0_slope = None
    if voiced.size > 4:
        f0_iqr = float(np.percentile(voiced, 75) - np.percentile(voiced, 25))
        # Linear slope of F0 across voiced frames (Hz/sec)
        voiced_idx = np.where(f0 > 0)[0]
        if voiced_idx.size > 4:
            t = voiced_idx * 0.01
            try:
                slope, _ = np.polyfit(t, voiced, 1)
                f0_slope = float(slope)
            except Exception:
                f0_slope = None

    # ── MFCC vector (mean over time) for spectral-envelope tracking ─
    mfcc_vec = None
    try:
        # 13 coefficients, classic for speech
        mfcc_obj = sound.to_mfcc(number_of_coefficients=13)
        mfcc_mat = mfcc_obj.to_array()  # shape: (n_coeffs+1, n_frames)
        # Drop coefficient 0 (energy) — sensitive to absolute loudness,
        # which we already track via intensity_mean.
        if mfcc_mat.shape[0] > 1 and mfcc_mat.shape[1] > 0:
            mfcc_vec = mfcc_mat[1:].mean(axis=1).astype(float).tolist()
    except Exception:
        mfcc_vec = None

    return {
        "f0_mean": f0_mean,
        "f0_std": f0_std,
        "f0_iqr": f0_iqr,
        "f0_slope": f0_slope,
        "jitter_local": jitter_local,
        "shimmer_local": shimmer_local,
        "hnr": hnr,
        "intensity_mean": intensity_mean,
        "intensity_std": intensity_std,
        "speaking_rate": speaking_rate,
        "pause_ratio": pause_ratio,
        "mfcc_vec": mfcc_vec,
        "duration_sec": float(total_sec),
    }


# ── Audio-quality checks ────────────────────────────────────────────
# Garbage-in / garbage-out is the silent failure mode of every VSA tool.
# These checks refuse to pretend a clipped or noisy recording is scoreable.
CLIPPING_THRESHOLD = 0.99          # samples at >|0.99| count as clipped
CLIPPING_PCT_BAD = 0.005           # >0.5 % clipped samples = clipped clip
SNR_BAD_DB = 12.0                  # below this = unreliable scoring
HNR_BAD_DB = 8.0                   # mean HNR below this = poor mic / room


def audio_quality(audio: np.ndarray, fs: int) -> dict:
    """Cheap sanity checks on input audio. Returns:
        {clipping_pct, snr_db, ok, warnings}
    Used by analyzer.* to refuse-or-warn on garbage input before features
    get computed and a fake-confident score gets displayed.
    """
    out = {"clipping_pct": 0.0, "snr_db": None, "ok": True, "warnings": []}
    if audio.size == 0:
        out["ok"] = False
        out["warnings"].append("empty audio")
        return out

    # Normalize to float in [-1, 1] for clipping check
    a = audio.astype(np.float32, copy=False)
    if np.max(np.abs(a)) > 1.5:           # likely int16, not normalized
        a = a / 32768.0
    clip_count = int(np.sum(np.abs(a) >= CLIPPING_THRESHOLD))
    clip_pct = float(clip_count / a.size)
    out["clipping_pct"] = clip_pct
    if clip_pct > CLIPPING_PCT_BAD:
        out["ok"] = False
        out["warnings"].append(
            f"clipping: {clip_pct * 100:.1f}% of samples at the rail"
        )

    # SNR estimate: RMS of quietest 10% frames vs RMS of loudest 50%
    frame_n = max(1, int(fs * 0.1))       # 100 ms frames
    n_frames = a.size // frame_n
    if n_frames >= 4:
        frames = a[:n_frames * frame_n].reshape(n_frames, frame_n)
        rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
        rms_sorted = np.sort(rms)
        noise = float(np.mean(rms_sorted[: max(1, n_frames // 10)]))
        signal = float(np.mean(rms_sorted[n_frames // 2:]))
        if noise > 0 and signal / noise > 1.5:
            # Skip the SNR judgment on uniform-amplitude signals (sine waves,
            # continuous tones) where there's no quiet baseline to measure
            # against. Real speech has pauses → meaningful signal/noise gap.
            snr_db = 20.0 * float(np.log10(signal / noise))
            out["snr_db"] = snr_db
            if snr_db < SNR_BAD_DB:
                out["ok"] = False
                out["warnings"].append(
                    f"low SNR: {snr_db:.1f} dB (need ≥ {SNR_BAD_DB:.0f})"
                )
    return out
