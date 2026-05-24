#!/usr/bin/env python3
"""
ECHO ML confirmation layer.

A trained RandomForest (MFCC features) that verifies a rule-based detection is
actually a drone and not speech/noise. Used as an opt-in confirmation gate:
the rules find a candidate fast; this confirms the timbre before alerting.

Model: echo_drone_clf.joblib (trained on real drone audio vs noise; rejects
speech-like signals). Feature pipeline MUST match training exactly:
  - audio resampled to 16 kHz
  - 512-sample Hann frames, 256 hop
  - 26-band mel log-power -> 13 DCT coeffs -> mean+std over frames (26-dim)

Requires: numpy, scikit-learn, joblib. Degrades gracefully (returns None) if
the model or libs are missing, so the rule-based detector keeps working.
"""

import os
import numpy as np

_MODEL = None
_FB = None
_ML_FS = 16000


def _available():
    return os.path.exists(os.path.join(os.path.dirname(__file__), "echo_drone_clf.joblib"))


def _load_model():
    global _MODEL
    if _MODEL is None:
        import joblib
        _MODEL = joblib.load(os.path.join(os.path.dirname(__file__), "echo_drone_clf.joblib"))
    return _MODEL


def _melfb(nfft=512, nmel=26, fs=_ML_FS):
    def hz2mel(f): return 2595 * np.log10(1 + f / 700)
    def mel2hz(m): return 700 * (10 ** (m / 2595) - 1)
    pts = mel2hz(np.linspace(hz2mel(0), hz2mel(fs / 2), nmel + 2))
    bins = np.floor((nfft + 1) * pts / fs).astype(int)
    fb = np.zeros((nmel, nfft // 2 + 1))
    for m in range(1, nmel + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        for k in range(l, c):
            fb[m - 1, k] = (k - l) / (c - l + 1e-9)
        for k in range(c, r):
            fb[m - 1, k] = (r - k) / (r - c + 1e-9)
    return fb


def _mfcc_feat(x16):
    global _FB
    if _FB is None:
        _FB = _melfb()
    win, hop = 512, 256
    w = np.hanning(win)
    frames = []
    for s in range(0, len(x16) - win, hop):
        seg = (x16[s:s + win] - x16[s:s + win].mean()) * w
        sp = np.abs(np.fft.rfft(seg)) ** 2
        mel = np.log(_FB @ sp + 1e-9)
        frames.append(np.fft.rfft(mel).real[:13])
    if not frames:
        return None
    frames = np.array(frames)
    return np.concatenate([frames.mean(0), frames.std(0)])


def drone_probability(block, fs_in=44100):
    """Return P(drone) in [0,1] for an audio block, or None if unavailable."""
    if not _available():
        return None
    try:
        x = block[:, 0] if getattr(block, "ndim", 1) > 1 else block
        x = np.asarray(x, dtype=np.float32)
        if fs_in != _ML_FS:
            n2 = max(512, int(len(x) * _ML_FS / fs_in))
            x = np.interp(np.linspace(0, len(x) - 1, n2), np.arange(len(x)), x)
        ft = _mfcc_feat(x)
        if ft is None or not np.all(np.isfinite(ft)):
            return None
        return float(_load_model().predict_proba([ft])[0][1])
    except Exception:
        return None
