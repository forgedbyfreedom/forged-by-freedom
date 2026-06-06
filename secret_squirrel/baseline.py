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
HIGH_IS_STRESS = {"jitter_local", "shimmer_local", "f0_std", "f0_iqr",
                  "intensity_std", "pause_ratio", "mfcc_distance",
                  "disfluency_rate", "hedge_rate"}

# Features where LOWER values = more stress
LOW_IS_STRESS = {"hnr", "first_person_rate"}

# Features where any deviation (|z|) counts — direction is individual-dependent
TWO_TAILED = {"f0_mean", "f0_slope", "speaking_rate", "intensity_mean",
              "words_per_sec"}

# Weighting from systematic-review consensus on what tracks stress most reliably
WEIGHTS = {
    # Acoustic stress channel
    "jitter_local":      0.13,
    "shimmer_local":     0.11,
    "hnr":               0.09,
    "f0_std":            0.06,
    "f0_iqr":            0.05,
    "f0_slope":          0.03,
    "f0_mean":           0.06,
    "intensity_std":     0.04,
    "speaking_rate":     0.04,
    "pause_ratio":       0.04,
    "mfcc_distance":     0.08,
    # Content channel — present only when whisper is installed.
    # Hedging is the single strongest deception correlate in the
    # Vrij/Pennebaker literature, so it gets a real weight.
    "disfluency_rate":   0.07,
    "hedge_rate":        0.10,
    "first_person_rate": 0.06,
    "words_per_sec":     0.04,
}

# Feature-aware minimum sigma — prevents z-score explosion when baseline samples
# are very uniform (especially with synthetic audio or very short calibrations).
# Values are the smallest within-speaker variation we expect in normal speech.
NOISE_FLOORS = {
    "jitter_local":      0.0015,
    "shimmer_local":     0.005,
    "hnr":               1.5,
    "f0_mean":           5.0,
    "f0_std":            3.0,
    "f0_iqr":            4.0,
    "f0_slope":          3.0,
    "intensity_mean":    1.5,
    "intensity_std":     0.8,
    "speaking_rate":     0.4,
    "pause_ratio":       0.06,
    "mfcc_distance":     0.5,
    "disfluency_rate":   0.03,
    "hedge_rate":        0.02,
    "first_person_rate": 0.03,
    "words_per_sec":     0.4,
}

# Cap how much any single feature can contribute (in σ units) — avoids one
# blown-up feature dominating the composite score.
CONTRIB_CAP = 4.0


class Baseline:
    """Collect baseline samples, then score subsequent utterances."""

    def __init__(self):
        self.samples: list[dict] = []
        self.stats: dict[str, tuple[float, float]] = {}  # k → (mean, std)
        self.mfcc_centroid: Optional[np.ndarray] = None
        self.locked: bool = False

    def add(self, features: dict) -> None:
        if self.locked or not features:
            return
        self.samples.append(features)

    def lock(self) -> dict:
        """Compute mean/std per feature and MFCC centroid from collected samples."""
        if not self.samples:
            return {}

        # ── MFCC centroid + within-baseline MFCC distance distribution ─
        mfcc_vecs = [np.asarray(s["mfcc_vec"]) for s in self.samples
                     if s.get("mfcc_vec") is not None]
        mfcc_dists = []
        if mfcc_vecs:
            self.mfcc_centroid = np.mean(np.stack(mfcc_vecs), axis=0)
            mfcc_dists = [float(np.linalg.norm(v - self.mfcc_centroid))
                          for v in mfcc_vecs]
            # Inject mfcc_distance into each baseline sample so it's stat-tracked
            for s, d in zip([s for s in self.samples if s.get("mfcc_vec") is not None],
                            mfcc_dists):
                s["mfcc_distance"] = d

        keys = set().union(*[set(s.keys()) for s in self.samples])
        for k in keys:
            if k == "mfcc_vec":
                continue  # vector, not scalar
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

    def mfcc_distance(self, features: dict) -> Optional[float]:
        """Euclidean distance from this sample's MFCC vector to baseline centroid."""
        if self.mfcc_centroid is None:
            return None
        v = features.get("mfcc_vec")
        if v is None:
            return None
        try:
            return float(np.linalg.norm(np.asarray(v) - self.mfcc_centroid))
        except Exception:
            return None

    def score(self, features: dict) -> dict:
        """Return composite stress score 0–100 + per-feature contributions.

        Composite uses a soft squash: weighted average |z| → 1 − exp(−z̄) → ×100.
        Caps at 100. NOT a probability of deception.
        """
        if not self.stats or not features:
            return {"composite": None, "per_feature": {}, "note": "no baseline"}

        # Inject derived mfcc_distance so it scores like any other feature
        features = dict(features)
        if "mfcc_distance" not in features:
            d = self.mfcc_distance(features)
            if d is not None:
                features["mfcc_distance"] = d

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
    """Map composite stress 0–100 to a four-band label.

    Note: these labels (accurate / baseline / deception / extreme) are
    interpretive shorthand chosen by the user. The underlying signal is still
    just "deviation from baseline acoustic + content features." Stress has
    many non-deceptive causes; do not treat any single reading as proof.
    """
    if composite < 25:
        return "accurate"
    if composite < 50:
        return "baseline"
    if composite < 75:
        return "deception"
    return "extreme"
