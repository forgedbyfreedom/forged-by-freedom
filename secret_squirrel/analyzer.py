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
from typing import Optional

import numpy as np
import parselmouth

from .features import extract_features
from .content import transcribe, content_features

TARGET_FS = 16000
MIN_DURATION_SEC = 0.5
TIMELINE_WIN_SEC = 1.0
TIMELINE_HOP_SEC = 0.5


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


def _response_latency(audio: np.ndarray, fs: int,
                      energy_threshold: float = 0.005) -> Optional[float]:
    """Seconds from start of clip until the first non-silent frame.

    Cheap proxy for live response latency: the gap before the subject begins
    speaking. Uses simple RMS thresholding on 30 ms frames.
    """
    if audio.size == 0:
        return None
    frame_n = int(fs * 0.03)
    if frame_n <= 0:
        return None
    n_frames = audio.size // frame_n
    for i in range(n_frames):
        frame = audio[i * frame_n:(i + 1) * frame_n]
        rms = float(np.sqrt(np.mean(frame * frame)))
        if rms > energy_threshold:
            return float(i * 0.03)
    return None


def _within_answer_timeline(audio: np.ndarray, fs: int, baseline,
                            win_sec: float = TIMELINE_WIN_SEC,
                            hop_sec: float = TIMELINE_HOP_SEC,
                            words: Optional[list] = None) -> list:
    """Slide a window across the answer; return [{t, composite, level, words}, …].

    A flat timeline = uniform stress across the answer. A spike mid-answer is
    where the speaker's voice changed — often where a fabrication is
    constructed or a difficult recall happens. This is for interpretation,
    not classification.

    When `words` is passed (Whisper word-timestamps, list of (start, end, word)),
    each timeline point is annotated with the words spoken during that window,
    so a spike at t=4.2s shows you WHICH WORDS were spoken when the spike
    occurred.
    """
    if not baseline.locked or audio.size < fs * win_sec:
        return []
    win = int(fs * win_sec)
    hop = int(fs * hop_sec)
    out = []
    for start in range(0, audio.size - win + 1, hop):
        chunk = audio[start:start + win]
        try:
            feats = extract_features(chunk, fs)
            score = baseline.score(feats)
        except Exception:
            continue
        if score.get("composite") is None:
            continue
        t = start / fs
        point = {
            "t": round(t, 2),
            "composite": float(score["composite"]),
            "level": score.get("level"),
        }
        if words:
            # Words whose midpoint falls within this window
            window_words = []
            t_end = t + win_sec
            for w in words:
                w_start, w_end, w_text = w
                w_mid = (w_start + w_end) / 2.0
                if t <= w_mid < t_end:
                    window_words.append(w_text)
            if window_words:
                point["words"] = " ".join(window_words).strip()
        out.append(point)
    return out


def analyze_audio_array(audio: np.ndarray, fs: int, engine,
                        mode: str = "question", label: str = "",
                        question_type: str = "target",
                        question_start_time: Optional[float] = None,
                        transcribe_enabled: bool = True) -> dict:
    """Run features → baseline add OR score → append to history.

    mode == "calibrate": chunk into 5s windows, add to baseline, then lock.
                         (Preserves history; engine.baseline replaced.)
    mode == "question":  extract whole-utterance features, score, transcribe if
                         enabled, compute within-answer timeline, push record.
    """
    if audio.size < fs * MIN_DURATION_SEC:
        return {"error": "audio too short"}

    if mode == "calibrate":
        # Replace baseline but KEEP history (multiple-baselines workflow)
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
                # Also transcribe baseline chunks so content features
                # have a baseline distribution (otherwise they're un-scored).
                if transcribe_enabled and feats:
                    try:
                        tx = transcribe(chunk, fs)
                        if tx:
                            cf = content_features(tx, chunk.size / fs)
                            for k in ("words_per_sec", "first_person_rate",
                                      "hedge_rate", "disfluency_rate"):
                                if cf.get(k) is not None:
                                    feats[k] = cf[k]
                    except Exception as e:
                        print(f"[squirrel] cal transcribe failed: {e}")
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

    duration_sec = float(audio.size / fs)
    try:
        feats = extract_features(audio, fs)
    except Exception as e:
        return {"error": f"feature extraction failed: {e}"}

    # Content channel (whisper) — adds words_per_sec, hedge_rate, etc. to feats
    content = None
    tx_words = None
    if transcribe_enabled:
        try:
            tx = transcribe(audio, fs)
            if tx:
                content = content_features(tx, duration_sec)
                tx_words = tx.get("words")
                # Merge scalar content features into feats for scoring
                for k in ("words_per_sec", "first_person_rate", "hedge_rate",
                          "disfluency_rate"):
                    if content.get(k) is not None:
                        feats[k] = content[k]
        except Exception as e:
            print(f"[squirrel] content extraction failed: {e}")

    score = engine.baseline.score(feats)
    timeline = _within_answer_timeline(audio, fs, engine.baseline,
                                       words=tx_words)
    latency = _response_latency(audio, fs)
    if question_start_time is not None:
        # Caller knows the wall-clock moment they asked the question
        latency = max(0.0, (time.time() - question_start_time))

    record = {
        "label": label or f"Q{len(engine.history) + 1}",
        "type": question_type,
        "timestamp": time.time(),
        "duration_sec": duration_sec,
        "response_latency_sec": latency,
        "features": feats,
        "score": score,
        "timeline": timeline,
        "content": content,
        "source": "offline",
    }
    with engine._lock:
        engine.history.append(record)
        if engine.state == "idle":
            engine.state = "ready"
    return {"ok": True, "mode": "question", "record": record}


def analyze_file(path: str, engine, mode: str = "question",
                 label: str = "", question_type: str = "target",
                 transcribe_enabled: bool = True) -> dict:
    if not os.path.exists(path):
        return {"error": f"file not found: {path}"}
    try:
        audio, fs = load_audio(path)
    except Exception as e:
        return {"error": f"load failed: {e}"}
    return analyze_audio_array(audio, fs, engine, mode=mode,
                               label=label or path,
                               question_type=question_type,
                               transcribe_enabled=transcribe_enabled)


def analyze_url(url: str, engine, mode: str = "question",
                label: str = "", question_type: str = "target",
                transcribe_enabled: bool = True) -> dict:
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
    return analyze_audio_array(audio, fs, engine, mode=mode,
                               label=label or url,
                               question_type=question_type,
                               transcribe_enabled=transcribe_enabled)
