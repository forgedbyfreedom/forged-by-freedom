#!/usr/bin/env python3
"""
ECHO — acoustic detection engine.

Refactor of the prototype detector into a reusable engine that produces a
structured result dict per audio block (instead of printing). Both the CLI
and the dashboard consume these results.

Result dict per block:
{
  "t": <seconds since start>,
  "detected": bool,            # persistence-confirmed drone
  "bpf": float|None,           # blade-pass fundamental, Hz
  "harmonics": int,
  "snr_db": float,
  "rpm2": int, "rpm3": int,    # implied RPM for 2- / 3-blade
  "multirotor": bool,
  "beat_hz": float|None,
  "wobble_pct": float|None,
  "wobble_rate_hz": float|None,
  "drone_like": bool,          # wobble consistent with flight
  "bearing_deg": float|None,
  "bearing_conf": float|None,
  "level_db": float,           # broadband input level (for the meter)
}
"""

from collections import deque
import numpy as np

FS = 44100
BLOCK = 16384
F0_LOW, F0_HIGH = 50, 700
BEAT_MIN, BEAT_MAX = 0.5, 25
HARMONICS = [1, 2, 3, 4, 5, 6]
HARMONIC_SNR_DB = 8.0
F0_TOLERANCE = 12.0
SPEED_OF_SOUND = 343.0

GEOMETRIES = {
    "respeaker": np.array([[0.0463, 0.0], [0.0, 0.0463],
                           [-0.0463, 0.0], [0.0, -0.0463]]),
    "stereo15cm": np.array([[-0.075, 0.0], [0.075, 0.0]]),
}


def _median_floor(mag, win=51):
    pad = win // 2
    padded = np.pad(mag, pad, mode="edge")
    strided = np.lib.stride_tricks.as_strided(
        padded, shape=(len(mag), win),
        strides=(padded.strides[0], padded.strides[0]))
    return np.median(strided, axis=1)


def find_candidates(mag, freqs, min_harmonics):
    floor = np.maximum(_median_floor(mag, 51), 1e-9)
    snr = 20 * np.log10(mag / floor)
    bin_hz = FS / BLOCK
    band = (freqs >= F0_LOW) & (freqs <= F0_HIGH)
    idx = np.where(band & (snr > HARMONIC_SNR_DB))[0]
    cands = []
    for i in idx:
        f0 = freqs[i]
        if f0 <= 0:
            continue
        hits, snrs = 0, []
        for h in HARMONICS:
            fh = f0 * h
            if fh >= freqs[-1]:
                break
            j = int(round(fh / bin_hz))
            local = snr[max(0, j - 1):min(len(snr) - 1, j + 1) + 1].max()
            if local > HARMONIC_SNR_DB:
                hits += 1
                snrs.append(local)
        if hits >= min_harmonics:
            cands.append((f0, hits, float(np.mean(snrs))))
    cands.sort(key=lambda c: (c[1], c[2]), reverse=True)
    # dedup near-duplicates / integer harmonics
    kept = []
    for c in cands:
        if not any(abs(c[0] - k[0]) <= F0_TOLERANCE
                   or abs(c[0] / k[0] - round(c[0] / k[0])) < 0.04 for k in kept):
            kept.append(c)
    return kept


def find_multirotor_beat(cands):
    strong = [c for c in cands if c[1] >= 3][:5]
    best = None
    for a in range(len(strong)):
        for b in range(a + 1, len(strong)):
            beat = abs(strong[a][0] - strong[b][0])
            if BEAT_MIN <= beat <= BEAT_MAX:
                score = strong[a][2] + strong[b][2]
                if best is None or score > best[3]:
                    best = (min(strong[a][0], strong[b][0]),
                            max(strong[a][0], strong[b][0]), beat, score)
    return best[:3] if best else None


class PersistenceTracker:
    def __init__(self, persist_sec, block_sec, hit_ratio=0.6):
        self.need = max(2, int(persist_sec / block_sec))
        self.hit_ratio = hit_ratio
        self.hist = deque(maxlen=self.need)

    def update(self, f0):
        self.hist.append(f0)
        present = [f for f in self.hist if f is not None]
        if len(self.hist) < self.need or not present:
            return None
        ref = float(np.median(present))
        agree = sum(1 for f in present if abs(f - ref) <= F0_TOLERANCE)
        return ref if agree / self.need >= self.hit_ratio else None


class ModulationTracker:
    def __init__(self, block_sec, window_sec=4.0):
        self.block_sec = block_sec
        self.f0s = deque(maxlen=max(8, int(window_sec / block_sec)))

    def update(self, f0):
        self.f0s.append(f0 if f0 is not None else np.nan)
        good = np.array([v for v in self.f0s if not np.isnan(v)])
        if len(good) < 6 or good.mean() <= 0:
            return None
        detr = good - good.mean()
        depth = 100.0 * detr.std() / good.mean()
        spec = np.abs(np.fft.rfft(detr * np.hanning(len(detr))))
        axis = np.fft.rfftfreq(len(detr), self.block_sec)
        rate = float(axis[1 + np.argmax(spec[1:])]) if len(spec) > 1 else 0.0
        return depth, rate


def gcc_phat(a, b, n_fft):
    A, B = np.fft.rfft(a, n_fft), np.fft.rfft(b, n_fft)
    R = A * np.conj(B)
    R /= np.maximum(np.abs(R), 1e-12)
    return np.fft.irfft(R, n_fft)


def _bandpass(x, fs, lo, hi):
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / fs)
    return np.fft.irfft(X * ((f >= lo) & (f <= hi)).astype(float)[:, None], n=n, axis=0)


def estimate_doa(block, mic_xy, fs, f0=None):
    n_ch = block.shape[1]
    if n_ch < 2:
        return None
    n_fft = 2 * block.shape[0]
    if f0:
        sig = _bandpass(block, fs, max(60, f0 * 0.7), min(fs / 2 - 1, f0 * 6))
    else:
        sig = _bandpass(block, fs, 80, 5000)
    pairs = [(i, j) for i in range(n_ch) for j in range(i + 1, n_ch)]
    ccs = {(i, j): gcc_phat(sig[:, i], sig[:, j], n_fft) for i, j in pairs}
    azs = np.deg2rad(np.arange(0, 360, 3))
    powers = []
    for az in azs:
        u = np.array([np.cos(az), np.sin(az)])
        p = 0.0
        for (i, j) in pairs:
            lag = int(round((mic_xy[i] - mic_xy[j]) @ u / SPEED_OF_SOUND * fs))
            p += ccs[(i, j)][lag % len(ccs[(i, j)])]
        powers.append(p)
    powers = np.array(powers)
    best = int(np.argmax(powers))
    conf = float(np.clip((powers.max() - powers.mean()) / (powers.std() + 1e-9) / 4.0, 0, 1))
    return float(np.rad2deg(azs[best]) % 360), conf


class EchoEngine:
    def __init__(self, min_harmonics=3, persist_sec=3.0, geometry=None):
        self.min_harmonics = min_harmonics
        self.persist = PersistenceTracker(persist_sec, BLOCK / FS)
        self.mod = ModulationTracker(BLOCK / FS)
        self.mic_xy = GEOMETRIES.get(geometry) if geometry else None
        self.n = 0

    def process(self, block):
        """block: 1-D or (samples, channels) float array. Returns a result dict."""
        self.n += 1
        multi = block.ndim > 1 and block.shape[1] >= 2
        mono = block[:, 0] if block.ndim > 1 else block
        level = 20 * np.log10(np.sqrt(np.mean(mono**2)) + 1e-9)
        x = (mono - np.mean(mono)) * np.hanning(len(mono))
        mag = np.abs(np.fft.rfft(x, n=BLOCK))
        freqs = np.fft.rfftfreq(BLOCK, 1 / FS)

        cands = find_candidates(mag, freqs, self.min_harmonics)
        res = cands[0] if cands else None
        beat = find_multirotor_beat(cands)
        f0 = res[0] if res else None
        locked = self.persist.update(f0)
        mod = self.mod.update(locked)

        out = {
            "t": round(self.n * BLOCK / FS, 2),
            "detected": locked is not None,
            "bpf": round(locked, 1) if locked else (round(f0, 1) if f0 else None),
            "harmonics": res[1] if res else 0,
            "snr_db": round(res[2], 1) if res else 0.0,
            "rpm2": int(locked * 30) if locked else None,
            "rpm3": int(locked * 20) if locked else None,
            "multirotor": beat is not None,
            "beat_hz": round(beat[2], 1) if beat else None,
            "wobble_pct": round(mod[0], 2) if mod else None,
            "wobble_rate_hz": round(mod[1], 1) if mod else None,
            "drone_like": bool(mod and 0.3 <= mod[0] <= 8 and mod[1] >= 0.3),
            "bearing_deg": None,
            "bearing_conf": None,
            "level_db": round(float(level), 1),
            "building": (res is not None) and (locked is None),
        }
        if locked and multi and self.mic_xy is not None:
            doa = estimate_doa(block, self.mic_xy, FS, f0=locked)
            if doa:
                out["bearing_deg"] = round(doa[0], 1)
                out["bearing_conf"] = round(doa[1], 2)
        return out
