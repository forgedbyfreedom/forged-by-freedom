"""Baseline calibration + per-feature z-score → composite stress score.

The honest theory: a per-subject baseline is the only meaningful reference for
acoustic stress because the absolute values vary enormously across people, mics,
rooms, and recording conditions. We score deviations from THIS subject's calm
speech, not against any universal norm.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np


# Features where HIGHER values = more stress (positive z is what we count)
HIGH_IS_STRESS = {"jitter_local", "shimmer_local", "f0_std",
                  "intensity_std", "pause_ratio"}

# Features where LOWER values = more stress
LOW_IS_STRESS = {"hnr"}

# Features where any deviation (|z|) counts — direction is individual-dependent
TWO_TAILED = {"f0_mean", "speaking_rate", "intensity_mean"}

# Weighting from systematic-review consensus on what tracks stress most reliably
WEIGHTS = {
    "jitter_local":    0.22,
    "shimmer_local":   0.18,
    "hnr":             0.15,
    "f0_std":          0.12,
    "f0_mean":         0.10,
    "intensity_std":   0.08,
    "speaking_rate":   0.08,
    "pause_ratio":     0.07,
}

# Feature-aware minimum sigma — prevents z-score explosion when baseline samples
# are very uniform (especially with synthetic audio or very short calibrations).
# Values are the smallest within-speaker variation we expect in normal speech.
NOISE_FLOORS = {
    "jitter_local":   0.0015,   # ~0.15 pct
    "shimmer_local":  0.005,    # ~0.5 pct
    "hnr":            1.5,      # dB
    "f0_mean":        5.0,      # Hz
    "f0_std":         3.0,      # Hz
    "intensity_mean": 1.5,      # dB
    "intensity_std":  0.8,      # dB
    "speaking_rate":  0.4,      # onsets/sec
    "pause_ratio":    0.06,     # 6 % of duration
}

# Cap how much any single feature can contribute (in σ units) — avoids one
# blown-up feature dominating the composite score.
CONTRIB_CAP = 4.0


class Baseline:
    """Collect baseline samples, then score subsequent utterances."""

    def __init__(self):
        self.samples: list[dict] = []
        self.stats: dict[str, tuple[float, float]] = {}  # k → (mean, std)
        self.locked: bool = False

    def add(self, features: dict) -> None:
        if self.locked or not features:
            return
        self.samples.append(features)

    def lock(self) -> dict:
        """Compute mean/std per feature from collected samples."""
        if not self.samples:
            return {}
        keys = set().union(*[set(s.keys()) for s in self.samples])
        for k in keys:
            vals = [s.get(k) for s in self.samples
                    if isinstance(s.get(k), (int, float))
                    and not math.isnan(s.get(k))]
            floor = NOISE_FLOORS.get(k, 1e-6)
            if len(vals) >= 2:
                mu = float(np.mean(vals))
                sigma = float(np.std(vals))
                self.stats[k] = (mu, max(sigma, floor))
            elif len(vals) == 1:
                self.stats[k] = (float(vals[0]), floor)
        self.locked = True
        return self.stats

    def score(self, features: dict) -> dict:
        """Return composite stress score 0–100 + per-feature contributions.

        Composite uses a soft squash: weighted average |z| → 1 − exp(−z̄) → ×100.
        Caps at 100. NOT a probability of deception.
        """
        if not self.stats or not features:
            return {"composite": None, "per_feature": {}, "note": "no baseline"}

        per_feature = {}
        weighted = 0.0
        weight_total = 0.0
        for k, w in WEIGHTS.items():
            v = features.get(k)
            stat = self.stats.get(k)
            if v is None or stat is None:
                continue
            mu, sigma = stat
            z = (v - mu) / sigma
            if k in HIGH_IS_STRESS:
                contrib = max(z, 0.0)
            elif k in LOW_IS_STRESS:
                contrib = max(-z, 0.0)
            else:
                contrib = abs(z)
            contrib = min(contrib, CONTRIB_CAP)
            per_feature[k] = {
                "value": v,
                "baseline_mean": mu,
                "baseline_std": sigma,
                "z": z,
                "stress_contrib": contrib,
            }
            weighted += w * contrib
            weight_total += w

        if weight_total <= 0:
            return {"composite": None, "per_feature": per_feature,
                    "note": "no overlap with baseline"}

        z_bar = weighted / weight_total
        # Squash: 1 - exp(-z_bar) maps z̄=0→0, 1→0.63, 2→0.86, 3→0.95
        composite = float(100.0 * (1.0 - math.exp(-z_bar)))
        composite = max(0.0, min(100.0, composite))

        return {
            "composite": composite,
            "z_bar": z_bar,
            "per_feature": per_feature,
            "level": _level(composite),
        }


def _level(composite: float) -> str:
    if composite < 40:
        return "low"
    if composite < 70:
        return "elevated"
    return "high"
