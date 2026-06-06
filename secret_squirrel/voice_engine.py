"""Secret Squirrel — voice stress engine.

Live mic → WebRTC VAD utterance segmentation → Parselmouth feature extraction
→ z-score vs calibrated baseline → composite stress score.

This is NOT a lie detector. It reports stress / cognitive-load markers.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:  # allow import-only environments
    sd = None

try:
    import webrtcvad
except Exception:
    webrtcvad = None

from .features import extract_features
from .baseline import Baseline


SAMPLE_RATE = 16000  # webrtcvad accepts 8/16/32 kHz; Parselmouth is happy here
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples
END_OF_UTTERANCE_SILENCE_MS = 1500
MAX_UTTERANCE_SEC = 60.0
MIN_UTTERANCE_SEC = 0.5
CALIBRATION_CHUNK_SEC = 5.0
MIN_CAL_DURATION_SEC = 5.0


class VoiceEngine:
    """State machine: idle → calibrating → ready → recording → ready."""

    def __init__(self):
        self.baseline = Baseline()
        self.history: list[dict] = []
        self.state: str = "idle"
        self._mode: Optional[str] = None  # "calibrate" | "question"
        self._buffer: list[np.ndarray] = []
        self._silence_ms: int = 0
        self._record_start: float = 0.0
        self._cal_duration: float = 30.0
        self._question_label: str = ""
        self._question_type: str = "target"
        self._first_voice_time: Optional[float] = None  # for response latency
        self._stream = None
        self._vad = webrtcvad.Vad(2) if webrtcvad else None
        self._lock = threading.Lock()

    # ── Public control ─────────────────────────────────────────────
    def start_calibration(self, duration_sec: float = 30.0) -> dict:
        if sd is None:
            return {"error": "sounddevice not installed"}
        if self.state not in ("idle", "ready"):
            return {"error": f"busy ({self.state})"}
        self.baseline = Baseline()
        with self._lock:
            self.state = "calibrating"
            self._mode = "calibrate"
            self._buffer = []
            self._silence_ms = 0
            self._record_start = time.time()
            self._cal_duration = max(MIN_CAL_DURATION_SEC, float(duration_sec))
        self._start_stream()
        return {"ok": True}

    def start_question(self, label: str = "",
                       question_type: str = "target") -> dict:
        if sd is None:
            return {"error": "sounddevice not installed"}
        if not self.baseline.locked:
            return {"error": "calibrate first"}
        if self.state != "ready":
            return {"error": f"busy ({self.state})"}
        if question_type not in ("control", "buffer", "target", "neutral"):
            question_type = "target"
        with self._lock:
            self.state = "recording"
            self._mode = "question"
            self._question_label = label or f"Q{len(self.history) + 1}"
            self._question_type = question_type
            self._buffer = []
            self._silence_ms = 0
            self._record_start = time.time()
            self._first_voice_time = None
        self._start_stream()
        return {"ok": True}

    def recalibrate(self, duration_sec: float = 30.0) -> dict:
        """Restart calibration but keep history. Used for multiple-baselines
        workflow when the speaker's calm state has drifted (fatigue, rapport)."""
        return self.start_calibration(duration_sec=duration_sec)

    def stop(self) -> dict:
        self._stop_stream()
        with self._lock:
            if self._mode == "calibrate":
                self._finalize_calibration_locked()
            elif self._mode == "question":
                self._finalize_question_locked()
            self.state = "ready" if self.baseline.locked else "idle"
            self._mode = None
        return {"ok": True}

    def reset(self) -> dict:
        self._stop_stream()
        with self._lock:
            self.baseline = Baseline()
            self.history = []
            self.state = "idle"
            self._mode = None
            self._buffer = []
        return {"ok": True}

    # ── Audio stream callbacks ─────────────────────────────────────
    def _start_stream(self):
        if self._stream is not None or sd is None:
            return
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            callback=self._on_audio,
        )
        self._stream.start()

    def _stop_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _on_audio(self, indata, frames, time_info, status):
        try:
            chunk = bytes(indata)
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0

            with self._lock:
                mode = self._mode
                if mode is None:
                    return
                self._buffer.append(samples)
                elapsed = time.time() - self._record_start

                if mode == "calibrate":
                    if elapsed >= self._cal_duration:
                        self._finalize_calibration_locked()
                        self.state = "ready"
                        self._mode = None
                        # stop the stream outside the lock
                        threading.Thread(target=self._stop_stream,
                                         daemon=True).start()
                    return

                # mode == "question"
                is_speech = False
                if self._vad is not None and len(chunk) == FRAME_SAMPLES * 2:
                    try:
                        is_speech = self._vad.is_speech(chunk, SAMPLE_RATE)
                    except Exception:
                        is_speech = False
                if is_speech:
                    self._silence_ms = 0
                    if self._first_voice_time is None:
                        self._first_voice_time = time.time()
                else:
                    self._silence_ms += FRAME_MS

                if (elapsed > MIN_UTTERANCE_SEC and
                        self._silence_ms >= END_OF_UTTERANCE_SILENCE_MS):
                    self._finalize_question_locked()
                    self.state = "ready"
                    self._mode = None
                    threading.Thread(target=self._stop_stream,
                                     daemon=True).start()
                elif elapsed > MAX_UTTERANCE_SEC:
                    self._finalize_question_locked()
                    self.state = "ready"
                    self._mode = None
                    threading.Thread(target=self._stop_stream,
                                     daemon=True).start()
        except Exception as e:
            print(f"[VoiceEngine] callback error: {e}")

    # ── Finalizers (must be called with self._lock held) ──────────
    def _finalize_calibration_locked(self):
        if not self._buffer:
            return
        audio = np.concatenate(self._buffer)
        if audio.size < SAMPLE_RATE * MIN_CAL_DURATION_SEC:
            return
        # Chunk baseline into CALIBRATION_CHUNK_SEC windows for multiple samples
        win = int(SAMPLE_RATE * CALIBRATION_CHUNK_SEC)
        n_chunks = max(1, audio.size // win)
        added = 0
        for i in range(n_chunks):
            chunk = audio[i * win: (i + 1) * win]
            if chunk.size < SAMPLE_RATE * 1.0:
                continue
            try:
                feats = extract_features(chunk, SAMPLE_RATE)
                if feats:
                    self.baseline.add(feats)
                    added += 1
            except Exception as e:
                print(f"[VoiceEngine] baseline chunk failed: {e}")
        if added > 0:
            self.baseline.lock()

    def _finalize_question_locked(self):
        if not self._buffer:
            return
        audio = np.concatenate(self._buffer)
        latency = (self._first_voice_time - self._record_start
                   if self._first_voice_time is not None else None)
        record = {
            "label": self._question_label,
            "type": self._question_type,
            "timestamp": time.time(),
            "duration_sec": float(audio.size / SAMPLE_RATE),
            "response_latency_sec": latency,
            "source": "live",
        }
        if audio.size < SAMPLE_RATE * MIN_UTTERANCE_SEC:
            record["error"] = "audio too short"
        else:
            try:
                # Delegate to analyzer for transcription + timeline + scoring,
                # but we already have features here — keep the cheap path.
                from .analyzer import (_within_answer_timeline,
                                       _response_latency)
                from .content import transcribe, content_features

                feats = extract_features(audio, SAMPLE_RATE)
                duration_sec = audio.size / SAMPLE_RATE
                content = None
                try:
                    tx = transcribe(audio, SAMPLE_RATE)
                    if tx:
                        content = content_features(tx, duration_sec)
                        for k in ("words_per_sec", "first_person_rate",
                                  "hedge_rate", "disfluency_rate"):
                            if content.get(k) is not None:
                                feats[k] = content[k]
                except Exception as e:
                    print(f"[VoiceEngine] content failed: {e}")
                record["features"] = feats
                record["score"] = self.baseline.score(feats)
                record["timeline"] = _within_answer_timeline(
                    audio, SAMPLE_RATE, self.baseline)
                record["content"] = content
                # If VAD missed the first voice frame, fall back to RMS proxy
                if record["response_latency_sec"] is None:
                    record["response_latency_sec"] = _response_latency(
                        audio, SAMPLE_RATE)
            except Exception as e:
                record["error"] = f"feature extraction failed: {e}"
        self.history.append(record)

    # ── Read-only snapshot for dashboard ───────────────────────────
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "mode": self._mode,
                "baseline_locked": self.baseline.locked,
                "baseline_samples": len(self.baseline.samples),
                "baseline_stats": dict(self.baseline.stats),
                "history_count": len(self.history),
                "history": list(self.history[-20:]),
                "now_recording_for_sec": (time.time() - self._record_start
                                          if self._mode else 0.0),
            }
