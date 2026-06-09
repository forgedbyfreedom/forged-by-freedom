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
    # Acoustic channel — speaker-variable features get less weight than the
    # 2025-06 round because real-world recordings showed f0_mean and shimmer
    # spiking on innocent answers when the baseline conditions (mic distance,
    # speaking volume) didn't perfectly match the question conditions.
    "jitter_local":      0.10,
    "shimmer_local":     0.08,
    "hnr":               0.09,
    "f0_std":            0.04,
    "f0_iqr":            0.04,
    "f0_slope":          0.02,
    "f0_mean":           0.02,  # absolute pitch is heavily speaker-style dependent
    "intensity_std":     0.03,
    "speaking_rate":     0.03,
    "pause_ratio":       0.05,
    "mfcc_distance":     0.12,  # promoted — most condition-stable
    # Content channel — promoted further, these are the most consistent
    # deception correlates in the Vrij / Pennebaker literature.
    "disfluency_rate":   0.10,
    "hedge_rate":        0.16,
    "first_person_rate": 0.07,
    "words_per_sec":     0.05,
}

# Feature-aware minimum sigma — prevents z-score explosion when baseline
# samples are uniform. Real-world subjects whose calibration and question
# conditions differ slightly (mic distance, mood, voice warm-up) produce
# 3-5σ deviations on the acoustic features even when answering honestly.
# These floors are calibrated against real human speech, not synthetic TTS.
NOISE_FLOORS = {
    "jitter_local":      0.015,
    "shimmer_local":     0.04,
    "hnr":               5.0,
    "f0_mean":           25.0,   # individuals' base pitch varies hugely
    "f0_std":            25.0,   # natural prosody varies hugely
    "f0_iqr":            20.0,
    "f0_slope":          15.0,
    "intensity_mean":    8.0,
    "intensity_std":     5.0,
    "speaking_rate":     1.5,
    "pause_ratio":       0.20,
    "mfcc_distance":     3.0,
    "disfluency_rate":   0.08,
    "hedge_rate":        0.08,
    "first_person_rate": 0.10,
    "words_per_sec":     1.2,
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
            return {"n_samples": n, "total_sec": total_sec,
                    "level": "none", "message": "Not calibrated yet."}
        if n < 2 or total_sec < 10:
            return {"n_samples": n, "total_sec": total_sec, "level": "bad",
                    "message": (f"Bad baseline ({n} samples, {total_sec:.0f}s). "
                                f"Scores will be unreliable. Recalibrate with "
                                f"≥20s of neutral speech.")}

        # Detect degenerate-condition baselines: too quiet, too low-pitched,
        # or too noisy. These cause every natural answer to read as "extreme"
        # because the question conditions differ from baseline conditions.
        bad = []
        f0m = self.stats.get("f0_mean")
        intm = self.stats.get("intensity_mean")
        hnrv = self.stats.get("hnr")
        if f0m and f0m[0] < 90:
            bad.append(f"low pitch ({f0m[0]:.0f} Hz — likely vocal fry / whispered)")
        if intm and intm[0] < 45:
            bad.append(f"recording quiet ({intm[0]:.0f} dB — move closer to the mic)")
        if hnrv and hnrv[0] < 10:
            bad.append(f"poor HNR ({hnrv[0]:.1f} dB — noisy room or low-quality mic)")
        if bad:
            return {"n_samples": n, "total_sec": total_sec, "level": "bad",
                    "message": (f"Baseline conditions look degenerate: {'; '.join(bad)}. "
                                f"Every answer recorded under normal conditions will "
                                f"score as extreme. Recalibrate at normal speaking "
                                f"volume, close to the mic, in a quieter room.")}

        if n < 4 or total_sec < 20:
            return {"n_samples": n, "total_sec": total_sec, "level": "warn",
                    "message": (f"Thin baseline ({n} samples, {total_sec:.0f}s). "
                                f"Recommended: ≥4 samples and ≥20s.")}
        return {"n_samples": n, "total_sec": total_sec, "level": "good",
                "message": f"Baseline locked ({n} samples, {total_sec:.0f}s)."}

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
