"""
ECHO RTSP audio source.

Pulls live audio (and on-demand video frames) from any RTSP URL via an
ffmpeg subprocess and yields numpy audio blocks for ECHO's existing
detection engine. One RtspAudioSource per camera.

Why ffmpeg + subprocess rather than a Python RTSP library:
  - ffmpeg handles every codec / container / network quirk in the wild;
    pure-Python RTSP libs are brittle on real correctional-facility
    cameras (mixed vendors, mixed firmware, h264 vs h265, etc.)
  - We can split audio and video tracks cleanly with -map flags
  - Bandwidth and CPU overhead are modest
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

import numpy as np


SAMPLE_RATE = 16000
BLOCK_SAMPLES = 16000 // 2  # 0.5s blocks, matches engine expectation


class RtspAudioSource:
    """Background thread that reads PCM audio from an RTSP URL via ffmpeg.

    Calls `on_block(numpy.ndarray)` for every 0.5s block of int16-as-float
    audio (mono, 16 kHz). Restarts ffmpeg automatically on stream drop.
    """

    def __init__(self,
                 rtsp_url: str,
                 on_block: Callable[[np.ndarray], None],
                 camera_name: str = "",
                 sample_rate: int = SAMPLE_RATE,
                 block_samples: int = BLOCK_SAMPLES,
                 reconnect_delay_sec: float = 5.0):
        self.rtsp_url = rtsp_url
        self.on_block = on_block
        self.camera_name = camera_name or rtsp_url
        self.sample_rate = sample_rate
        self.block_samples = block_samples
        self.reconnect_delay_sec = reconnect_delay_sec

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._last_block_time: float = 0.0
        self._consecutive_failures: int = 0
        self._total_blocks: int = 0

    # ── lifecycle ────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if shutil.which("ffmpeg") is None:
            raise RuntimeError(
                "ffmpeg not on PATH — required for RTSP audio ingestion. "
                "apt install ffmpeg / brew install ffmpeg / winget install Gyan.FFmpeg"
            )
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"rtsp-{self.camera_name}")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        if self._thread:
            self._thread.join(timeout=3)

    # ── status / health ──────────────────────────────────────────
    def health(self) -> dict:
        now = time.time()
        return {
            "camera": self.camera_name,
            "alive": bool(self._thread and self._thread.is_alive()),
            "last_block_age_sec": (now - self._last_block_time
                                   if self._last_block_time else None),
            "total_blocks": self._total_blocks,
            "consecutive_failures": self._consecutive_failures,
        }

    # ── ffmpeg loop ──────────────────────────────────────────────
    def _ffmpeg_cmd(self) -> list:
        # -rtsp_transport tcp is more reliable on lossy networks than UDP
        # -fflags nobuffer + -flags low_delay reduce latency
        # -vn drops video (we'll pull frames separately in echo_vision.py)
        # -ac 1 mono, -ar 16000, -f s16le raw int16 little-endian to stdout
        return [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-i", self.rtsp_url,
            "-vn",
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "s16le",
            "-",
        ]

    def _run(self) -> None:
        bytes_per_block = self.block_samples * 2  # int16 = 2 bytes/sample
        while not self._stop_event.is_set():
            try:
                self._proc = subprocess.Popen(
                    self._ffmpeg_cmd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0,
                )
                buf = b""
                while not self._stop_event.is_set():
                    chunk = self._proc.stdout.read(bytes_per_block - len(buf))
                    if not chunk:
                        break  # ffmpeg exited / stream dropped
                    buf += chunk
                    while len(buf) >= bytes_per_block:
                        block_bytes = buf[:bytes_per_block]
                        buf = buf[bytes_per_block:]
                        audio = (np.frombuffer(block_bytes, dtype=np.int16)
                                 .astype(np.float32) / 32768.0)
                        try:
                            self.on_block(audio)
                            self._total_blocks += 1
                            self._last_block_time = time.time()
                            self._consecutive_failures = 0
                        except Exception as e:
                            print(f"[rtsp:{self.camera_name}] on_block error: {e}")
            except Exception as e:
                print(f"[rtsp:{self.camera_name}] ffmpeg error: {e}")
            finally:
                self._consecutive_failures += 1
                try:
                    if self._proc:
                        self._proc.terminate()
                except Exception:
                    pass
                self._proc = None
            if not self._stop_event.is_set():
                # Exponential backoff capped at 60s
                delay = min(60.0, self.reconnect_delay_sec * (
                    1.5 ** min(10, self._consecutive_failures - 1)))
                print(f"[rtsp:{self.camera_name}] reconnecting in {delay:.1f}s "
                      f"(failure #{self._consecutive_failures})")
                self._stop_event.wait(delay)


def grab_jpeg_frame(rtsp_url: str, timeout_sec: float = 5.0) -> Optional[bytes]:
    """Pull a single still JPEG frame from an RTSP URL.

    Cheap, on-demand. Used by the dashboard to show a snapshot, and by the
    vision worker to grab a frame for YOLO inference. Returns JPEG bytes or
    None on failure.
    """
    if shutil.which("ffmpeg") is None:
        return None
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-frames:v", "1",
        "-f", "image2",
        "-vcodec", "mjpeg",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout_sec)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    return None
