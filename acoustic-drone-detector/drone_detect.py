#!/usr/bin/env python3
"""
Acoustic drone detector — harmonic stack + persistence + RPM modulation + DOA.

Detection layers:
  1. Harmonic stack   : blade-pass fundamental (50-700 Hz) with >=N harmonics.
                        50 Hz floor catches big slow props on heavy-lift builds.
  2. Persistence      : signature must hold for several seconds (default 3 s).
  3. Multi-rotor beat : two strong fundamentals a few Hz apart -> multiple
                        rotors slightly out of sync (hexa/octo heavy-lift cue).
                        Reliable as a binary flag; beat value is coarse.
  4. RPM modulation   : drones jitter RPM to hold position -> small rapid
                        wobble in the fundamental. Steady tones (HVAC, a fan
                        held at constant speed) do not. Strong confuser filter.
  5. Direction (DOA)  : with a multi-mic array, SRP-PHAT estimates azimuth so
                        you get a bearing and can reject diffuse background.
                        Coarse on a small array at low freq (see notes).

Usage:
  Single mic, live:    python3 drone_detect.py
  4-mic array, live:   python3 drone_detect.py --channels 4 --geometry respeaker
  Analyze a WAV:       python3 drone_detect.py --wav clip.wav
  Tune:                python3 drone_detect.py --min-harmonics 3 --persist-sec 2.5

WAV is mono or multi-channel 16-bit PCM. With >=2 channels and a geometry,
DOA is computed; otherwise DOA is skipped automatically.
"""

import argparse
from collections import deque

import numpy as np

# ── Audio / FFT config ───────────────────────────────────────────────
FS = 44100
BLOCK = 16384                 # ~0.37 s -> ~2.7 Hz resolution
F0_LOW, F0_HIGH = 50, 700     # blade-pass window (50 Hz catches big slow props)
BEAT_MIN, BEAT_MAX = 0.5, 25  # Hz; two rotors this far apart in BPF -> audible beat
HARMONICS = [1, 2, 3, 4, 5, 6]
HARMONIC_SNR_DB = 8.0
F0_TOLERANCE = 12.0           # Hz, for matching f0 across frames
SPEED_OF_SOUND = 343.0        # m/s

# ── Mic array geometries (x, y) in meters, planar ────────────────────
GEOMETRIES = {
    # ReSpeaker 4-Mic Array: ~circular, radius ~0.0463 m (measured center-to-mic)
    "respeaker": np.array([
        [ 0.0463,  0.0000],
        [ 0.0000,  0.0463],
        [-0.0463,  0.0000],
        [ 0.0000, -0.0463],
    ]),
    # Generic 2-mic stereo bar, 0.15 m apart (azimuth front/back ambiguous)
    "stereo15cm": np.array([
        [-0.075, 0.0],
        [ 0.075, 0.0],
    ]),
}


# ── Harmonic-stack core ──────────────────────────────────────────────
def _median_floor(mag, win=51):
    pad = win // 2
    padded = np.pad(mag, pad, mode="edge")
    # vectorized sliding median
    shape = (len(mag), win)
    strided = np.lib.stride_tricks.as_strided(
        padded, shape=shape, strides=(padded.strides[0], padded.strides[0])
    )
    return np.median(strided, axis=1)


def find_candidates(mag, freqs, min_harmonics):
    """Return all qualifying (f0, n_harmonics, mean_snr_db) sorted strongest-first."""
    floor = np.maximum(_median_floor(mag, win=51), 1e-9)
    snr = 20 * np.log10(mag / floor)
    bin_hz = FS / BLOCK

    band = (freqs >= F0_LOW) & (freqs <= F0_HIGH)
    cand_idx = np.where(band & (snr > HARMONIC_SNR_DB))[0]

    cands = []
    for i in cand_idx:
        f0 = freqs[i]
        if f0 <= 0:
            continue
        hits, snrs = 0, []
        for h in HARMONICS:
            fh = f0 * h
            if fh >= freqs[-1]:
                break
            j = int(round(fh / bin_hz))
            jlo, jhi = max(0, j - 1), min(len(snr) - 1, j + 1)
            local = snr[jlo:jhi + 1].max()
            if local > HARMONIC_SNR_DB:
                hits += 1
                snrs.append(local)
        if hits >= min_harmonics:
            cands.append((f0, hits, float(np.mean(snrs))))
    cands.sort(key=lambda c: (c[1], c[2]), reverse=True)
    return _dedup_candidates(cands)


def _dedup_candidates(cands):
    """Drop candidates that are near-duplicates / harmonics of a stronger one."""
    kept = []
    for c in cands:
        f0 = c[0]
        dup = False
        for k in kept:
            ratio = f0 / k[0]
            # same tone, or an integer-multiple harmonic of an already-kept tone
            if abs(f0 - k[0]) <= F0_TOLERANCE or abs(ratio - round(ratio)) < 0.04:
                dup = True
                break
        if not dup:
            kept.append(c)
    return kept


def find_fundamental(mag, freqs, min_harmonics):
    cands = find_candidates(mag, freqs, min_harmonics)
    return cands[0] if cands else None


def find_multirotor_beat(cands):
    """
    Two distinct strong fundamentals spaced BEAT_MIN..BEAT_MAX apart indicate
    multiple rotors running slightly out of sync (heavy-lift hexa/octo signature).
    Returns (f_a, f_b, beat_hz) for the strongest such pair, else None.
    """
    strong = [c for c in cands if c[1] >= 3][:5]
    best = None
    for a in range(len(strong)):
        for b in range(a + 1, len(strong)):
            fa, fb = strong[a][0], strong[b][0]
            beat = abs(fa - fb)
            if BEAT_MIN <= beat <= BEAT_MAX:
                score = strong[a][2] + strong[b][2]
                if best is None or score > best[3]:
                    best = (min(fa, fb), max(fa, fb), beat, score)
    return best[:3] if best else None


# ── Persistence ──────────────────────────────────────────────────────
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


# ── RPM-modulation analysis ──────────────────────────────────────────
class ModulationTracker:
    """
    Tracks the locked fundamental over time and characterizes its wobble.
    Returns (depth_pct, mod_rate_hz). Drone hover typically shows depth in the
    ~0.5-5% range with mod rates of a few Hz. A dead-steady tone -> depth ~0.
    """
    def __init__(self, block_sec, window_sec=4.0):
        self.block_sec = block_sec
        self.maxlen = max(8, int(window_sec / block_sec))
        self.f0s = deque(maxlen=self.maxlen)

    def update(self, f0):
        self.f0s.append(f0 if f0 is not None else np.nan)
        vals = np.array(self.f0s, dtype=float)
        good = vals[~np.isnan(vals)]
        if len(good) < 6:
            return None
        mean = good.mean()
        if mean <= 0:
            return None
        detr = good - mean
        depth_pct = 100.0 * detr.std() / mean
        # dominant modulation rate via FFT of the (uniformly sampled) f0 series
        spec = np.abs(np.fft.rfft(detr * np.hanning(len(detr))))
        rate_axis = np.fft.rfftfreq(len(detr), self.block_sec)
        mod_rate = float(rate_axis[1 + np.argmax(spec[1:])]) if len(spec) > 1 else 0.0
        return depth_pct, mod_rate


# ── Direction of arrival: GCC-PHAT + SRP-PHAT azimuth scan ───────────
def gcc_phat(a, b, n_fft):
    A = np.fft.rfft(a, n=n_fft)
    B = np.fft.rfft(b, n=n_fft)
    R = A * np.conj(B)
    R /= np.maximum(np.abs(R), 1e-12)        # PHAT weighting
    cc = np.fft.irfft(R, n=n_fft)
    return cc


def estimate_doa(block, mic_xy, fs, f0=None):
    """
    SRP-PHAT azimuth scan (planar array). Returns best azimuth in degrees
    (0 = +x axis, CCW positive) and a confidence in [0,1].
    block: (samples, channels)
    """
    n_ch = block.shape[1]
    if n_ch < 2:
        return None
    n_fft = 2 * block.shape[0]

    # band-limit around the drone signature to ignore wind/traffic energy
    if f0 is not None:
        sig = _bandpass(block, fs, max(60, f0 * 0.7), min(fs / 2 - 1, f0 * 6))
    else:
        sig = _bandpass(block, fs, 80, 5000)

    # precompute GCC-PHAT for each mic pair
    pairs = [(i, j) for i in range(n_ch) for j in range(i + 1, n_ch)]
    ccs = {(i, j): gcc_phat(sig[:, i], sig[:, j], n_fft) for i, j in pairs}
    half = n_fft // 2

    azimuths = np.deg2rad(np.arange(0, 360, 3))
    best_az, best_power = None, -np.inf
    for az in azimuths:
        u = np.array([np.cos(az), np.sin(az)])     # unit direction
        power = 0.0
        for (i, j) in pairs:
            # expected delay (s) for plane wave from direction u
            d = (mic_xy[i] - mic_xy[j]) @ u / SPEED_OF_SOUND
            lag = int(round(d * fs))
            idx = (lag + half) % n_fft
            cc = ccs[(i, j)]
            power += cc[(idx - half) % len(cc)]
        if power > best_power:
            best_power, best_az = power, az

    # crude confidence: peak vs mean over scan
    powers = []
    for az in azimuths:
        u = np.array([np.cos(az), np.sin(az)])
        p = 0.0
        for (i, j) in pairs:
            d = (mic_xy[i] - mic_xy[j]) @ u / SPEED_OF_SOUND
            lag = int(round(d * fs))
            cc = ccs[(i, j)]
            p += cc[(lag) % len(cc)]
        powers.append(p)
    powers = np.array(powers)
    conf = float(np.clip((powers.max() - powers.mean()) /
                         (powers.std() + 1e-9) / 4.0, 0, 1))
    return np.rad2deg(best_az) % 360, conf


def _bandpass(x, fs, lo, hi):
    """Lightweight FFT-domain bandpass (no scipy dependency)."""
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / fs)
    mask = ((f >= lo) & (f <= hi)).astype(float)[:, None]
    return np.fft.irfft(X * mask, n=n, axis=0)


# ── Per-block pipeline ───────────────────────────────────────────────
def analyze_block(block, args, trackers):
    persist, modtrk, mic_xy = trackers
    mono = block[:, 0] if block.ndim > 1 else block
    mono = mono - np.mean(mono)
    windowed = mono * np.hanning(len(mono))
    mag = np.abs(np.fft.rfft(windowed, n=BLOCK))
    freqs = np.fft.rfftfreq(BLOCK, 1 / FS)

    cands = find_candidates(mag, freqs, args.min_harmonics)
    res = cands[0] if cands else None
    beat = find_multirotor_beat(cands)
    f0 = res[0] if res else None
    locked = persist.update(f0)
    mod = modtrk.update(locked)

    if locked:
        rpm2, rpm3 = locked * 30, locked * 20
        # res can be None on a momentary gap while persistence still holds
        harm = res[1] if res else 0
        snr = res[2] if res else 0.0
        line = (f"[DETECT] BPF={locked:6.1f} Hz | harm={harm} "
                f"| SNR={snr:4.1f}dB | RPM≈{rpm2:.0f}(2bl)/{rpm3:.0f}(3bl)")
        if beat:
            line += f" | MULTI-ROTOR beat={beat[2]:4.1f}Hz ({beat[0]:.0f}/{beat[1]:.0f}Hz)"
        if mod:
            depth, rate = mod
            tag = "DRONE-LIKE" if 0.3 <= depth <= 8 and rate >= 0.3 else "steady?"
            line += f" | wobble={depth:4.2f}% @ {rate:3.1f}Hz [{tag}]"
        if block.ndim > 1 and block.shape[1] >= 2 and mic_xy is not None:
            doa = estimate_doa(block, mic_xy, FS, f0=locked)
            if doa:
                line += f" | bearing={doa[0]:5.1f}° (conf {doa[1]:.2f})"
        print(line)
    elif res:
        print(f"  candidate f0={res[0]:6.1f}Hz harm={res[1]} "
              f"snr={res[2]:4.1f}dB (building persistence...)")
    else:
        print("  .", end="", flush=True)


def make_trackers(args):
    persist = PersistenceTracker(args.persist_sec, BLOCK / FS)
    modtrk = ModulationTracker(BLOCK / FS)
    mic_xy = GEOMETRIES.get(args.geometry) if args.geometry else None
    return persist, modtrk, mic_xy


def run_live(args):
    import sounddevice as sd
    trackers = make_trackers(args)
    ch = args.channels
    print(f"Listening @ {FS} Hz, {ch}ch, {BLOCK/FS:.2f}s blocks. Ctrl-C to stop.")
    with sd.InputStream(channels=ch, samplerate=FS, blocksize=BLOCK) as stream:
        while True:
            data, _ = stream.read(BLOCK)
            analyze_block(data if ch > 1 else data[:, 0], args, trackers)


def run_wav(path, args):
    import wave
    trackers = make_trackers(args)
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, "expects 16-bit PCM WAV"
        fs, nch = w.getframerate(), w.getnchannels()
        audio = (np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                 .astype(np.float32) / 32768.0)
    if fs != FS:
        print(f"WARN: file is {fs} Hz; code tuned for {FS} Hz. Resample for accuracy.")
    audio = audio.reshape(-1, nch)
    block = audio if nch > 1 else audio[:, 0]
    step = BLOCK
    for s in range(0, len(audio) - step, step):
        analyze_block(block[s:s + step], args, trackers)


def main():
    ap = argparse.ArgumentParser(description="Acoustic drone detector")
    ap.add_argument("--wav", help="analyze a 16-bit PCM WAV instead of live mic")
    ap.add_argument("--channels", type=int, default=1, help="live input channels")
    ap.add_argument("--geometry", choices=list(GEOMETRIES), default=None,
                    help="mic array geometry for DOA (needs >=2 channels)")
    ap.add_argument("--min-harmonics", type=int, default=3)
    ap.add_argument("--persist-sec", type=float, default=3.0,
                    help="seconds the signature must persist (default 3.0; "
                         "heavy-lift loiters, so a longer window cuts false alarms)")
    args = ap.parse_args()
    try:
        run_wav(args.wav, args) if args.wav else run_live(args)
    except KeyboardInterrupt:
        print("\nstopped.")
    except Exception as e:          # safety net: don't die with a raw traceback
        print(f"\nERROR: {type(e).__name__}: {e}")
        print("   The drone detector encountered an unexpected error and has stopped.")
        print("   (Check your microphone/WAV file, audio permissions, or Python dependencies.)")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
