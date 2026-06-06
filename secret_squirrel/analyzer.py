"""Offline analysis: WAV file or video URL → features → baseline/score.

URLs are downloaded with yt-dlp (handles YouTube, X, Instagram, TikTok, Facebook,
direct media URLs, and ~1000 other sites). Audio is loaded and resampled via
Parselmouth — no scipy dependency.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import parselmouth

from .features import extract_features

TARGET_FS = 16000
MIN_DURATION_SEC = 0.5


def load_audio(path: str | os.PathLike) -> tuple[np.ndarray, int]:
    """Load any audio/video file Parselmouth can read; return mono 16 kHz float64."""
    sound = parselmouth.Sound(str(path))
    if sound.sampling_frequency != TARGET_FS:
        sound = sound.resample(TARGET_FS)
    arr = sound.values
    if arr.ndim == 2:
        arr = arr.mean(axis=0)  # downmix to mono
    return arr.astype(np.float64), TARGET_FS


def download_url(url: str, out_dir: str | None = None) -> str:
    """Download audio track from URL via yt-dlp; return path to a WAV file."""
    if shutil.which("yt-dlp") is None:
        raise RuntimeError(
            "yt-dlp not installed. Run: pip install yt-dlp  "
            "(also requires ffmpeg in PATH)"
        )
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found in PATH (required by yt-dlp).")

    out_dir = out_dir or tempfile.mkdtemp(prefix="sq_dl_")
    out_template = os.path.join(out_dir, f"audio_{int(time.time()*1000)}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "-x", "--audio-format", "wav",
        "--postprocessor-args", "-ar 16000 -ac 1",
        "-o", out_template,
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed ({proc.returncode}): {proc.stderr.strip()[:500]}"
        )
    wavs = sorted(Path(out_dir).glob("audio_*.wav"))
    if not wavs:
        raise RuntimeError("yt-dlp succeeded but no WAV was produced.")
    return str(wavs[-1])


def analyze_audio_array(audio: np.ndarray, fs: int, engine,
                        mode: str = "question", label: str = "") -> dict:
    """Run features → baseline add OR score → append to history.

    mode == "calibrate": chunk into 5s windows, add to baseline, then lock.
    mode == "question":  extract whole-utterance features, score, push to history.
    """
    if audio.size < fs * MIN_DURATION_SEC:
        return {"error": "audio too short"}

    if mode == "calibrate":
        # Replace any existing baseline
        from .baseline import Baseline
        engine.baseline = Baseline()
        win = int(fs * 5.0)
        n = max(1, audio.size // win)
        added = 0
        for i in range(n):
            chunk = audio[i * win:(i + 1) * win]
            if chunk.size < fs * 1.0:
                continue
            try:
                feats = extract_features(chunk, fs)
                if feats:
                    engine.baseline.add(feats)
                    added += 1
            except Exception as e:
                print(f"[squirrel] calibration chunk failed: {e}")
        if added == 0:
            return {"error": "no usable baseline chunks"}
        engine.baseline.lock()
        return {
            "ok": True,
            "mode": "calibrate",
            "baseline_samples": added,
            "duration_sec": float(audio.size / fs),
        }

    if not engine.baseline.locked:
        return {"error": "calibrate first"}

    try:
        feats = extract_features(audio, fs)
        score = engine.baseline.score(feats)
    except Exception as e:
        return {"error": f"feature extraction failed: {e}"}

    record = {
        "label": label or f"Q{len(engine.history) + 1}",
        "timestamp": time.time(),
        "duration_sec": float(audio.size / fs),
        "features": feats,
        "score": score,
        "source": "offline",
    }
    with engine._lock:
        engine.history.append(record)
        if engine.state == "idle":
            engine.state = "ready"
    return {"ok": True, "mode": "question", "record": record}


def analyze_file(path: str, engine, mode: str = "question",
                 label: str = "") -> dict:
    if not os.path.exists(path):
        return {"error": f"file not found: {path}"}
    try:
        audio, fs = load_audio(path)
    except Exception as e:
        return {"error": f"load failed: {e}"}
    return analyze_audio_array(audio, fs, engine, mode=mode, label=label or path)


def analyze_url(url: str, engine, mode: str = "question",
                label: str = "") -> dict:
    try:
        wav_path = download_url(url)
    except Exception as e:
        return {"error": str(e)}
    try:
        audio, fs = load_audio(wav_path)
    except Exception as e:
        return {"error": f"load failed: {e}"}
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass
    return analyze_audio_array(audio, fs, engine, mode=mode, label=label or url)
