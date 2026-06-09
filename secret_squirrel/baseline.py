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

# Feature-aware minimum sigma — prevents z-score explosion when baseline
# samples are uniform. These were originally too tight: a real-world subject's
# natural prosody varies more than a 30-second calibration window suggests,
# so question speech often produced 4σ deviations on perfectly innocent
# features. Doubled across the board after a real Windows deployment showed
# "everything looks extreme."
NOISE_FLOORS = {
    "jitter_local":      0.003,
    "shimmer_local":     0.012,
    "hnr":               3.0,
    "f0_mean":           10.0,
    "f0_std":            8.0,
    "f0_iqr":            10.0,
    "f0_slope":          6.0,
    "intensity_mean":    3.0,
    "intensity_std":     2.0,
    "speaking_rate":     0.8,
    "pause_ratio":       0.12,
    "mfcc_distance":     1.2,
    "disfluency_rate":   0.06,
    "hedge_rate":        0.04,
    "first_person_rate": 0.06,
    "words_per_sec":     0.8,
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
        # When the operator labels some history records as truth/lie and clicks
        # "Refit weights", these subject-specific weights override the defaults.
        # Set back to None to revert.
        self.custom_weights: Optional[dict[str, float]] = None

    def active_weights(self) -> dict[str, float]:
        return self.custom_weights if self.custom_weights else WEIGHTS

    def set_custom_weights(self, weights: dict[str, float]) -> None:
        # Normalize to sum to 1 so the squash function still maps reasonably
        total = sum(max(w, 0.0) for w in weights.values())
        if total <= 0:
            self.custom_weights = None
            return
        self.custom_weights = {k: max(w, 0.0) / total
                               for k, w in weights.items()}

    def clear_custom_weights(self) -> None:
        self.custom_weights = None

    def countermeasure_check(self, features: dict,
                             pct_threshold: float = 0.30) -> list[str]:
        """Flag possible deliberate gaming of the calibration.

        Subjects who learn about VSA tools sometimes speak deliberately
        monotonously / slowly during baseline so their natural speaking
        style during target questions reads as "elevated." We catch this
        by comparing question features that are easy to consciously
        manipulate (speaking rate, intensity) against the baseline mean.
        A shift > 30% in either direction is flagged.
        """
        if not self.locked:
            return []
        flags = []
        for k in ("speaking_rate", "intensity_mean"):
            v = features.get(k)
            stat = self.stats.get(k)
            if v is None or stat is None:
                continue
            mu, _ = stat
            if mu <= 0:
                continue
            pct = (v - mu) / mu
            if abs(pct) >= pct_threshold:
                direction = "faster/louder" if pct > 0 else "slower/quieter"
                flags.append(
                    f"{k}: {pct * 100:+.0f}% vs baseline ({direction})"
                )
        return flags

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

    def quality(self) -> dict:
        """Report how trustworthy the baseline is.

        Bad baselines silently produce bad scores. This surfaces the obvious
        red flags before the operator starts asking real questions:
          n_samples < 2  or  total_sec < 10  → bad   (recalibrate)
          n_samples < 4  or  total_sec < 20  → warn  (acceptable but thin)
          else                               → good
        """
        n = len(self.samples)
        total_sec = float(sum(s.get("duration_sec", 0.0) or 0.0
                              for s in self.samples))
        if not self.locked:
            level = "none"
            msg = "Not calibrated yet."
        elif n < 2 or total_sec < 10:
            level = "bad"
            msg = (f"Bad baseline ({n} samples, {total_sec:.0f}s). "
                   f"Scores will be unreliable. Recalibrate with ≥20s of "
                   f"neutral speech.")
        elif n < 4 or total_sec < 20:
            level = "warn"
            msg = (f"Thin baseline ({n} samples, {total_sec:.0f}s). "
                   f"Recommended: ≥4 samples and ≥20s of neutral speech.")
        else:
            level = "good"
            msg = f"Baseline locked ({n} samples, {total_sec:.0f}s)."
        return {"n_samples": n, "total_sec": total_sec,
                "level": level, "message": msg}

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
        for k, w in self.active_weights().items():
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

    Bands measure deviation from the subject's own calibrated baseline of
    acoustic + content features. Higher bands mean larger deviation; they do
    not name a verdict. Thresholds tuned for real-world subjects whose natural
    prosody fluctuates more than synthetic test data suggests.
    """
    if composite < 35:
        return "accurate"
    if composite < 60:
        return "baseline"
    if composite < 80:
        return "elevated"
    return "extreme"
