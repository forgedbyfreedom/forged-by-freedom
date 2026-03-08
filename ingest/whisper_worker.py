#!/usr/bin/env python3
"""
Persistent Whisper Worker — Forged by Freedom
==============================================
Loads the MLX Whisper model ONCE, then reads file paths from stdin
and transcribes them without ever reloading the model.

Protocol (stdin/stdout):
    IN:  /path/to/audio.mp3
    OUT: OK /path/to/audio.mp3
    OUT: FAIL /path/to/audio.mp3 error message

For long files (>30 min), splits into 30-min chunks using ffmpeg,
transcribes each chunk in-process (model stays loaded), and concatenates.

Has a per-file timeout (20 min) to prevent hangs on problematic files.

Usage:
    echo "/path/to/file.mp3" | python3 whisper_worker.py
    python3 whisper_worker.py < file_list.txt
"""

import os
import sys
import signal
import subprocess
from pathlib import Path

# Add ingest dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import mlx_whisper
from anabolics_vocabulary import get_whisper_prompt, correct_transcript

MODEL = "mlx-community/whisper-small-mlx"
CHUNK_THRESHOLD = 1800   # Files >30 min get chunked
CHUNK_DURATION = 1800    # 30-min chunks
FILE_TIMEOUT = 1200      # 20 min max per file (or per chunk)


class TranscriptionTimeout(Exception):
    pass


def timeout_handler(signum, frame):
    raise TranscriptionTimeout("Transcription timed out")


def get_duration(audio_path):
    """Get audio duration in seconds."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception:
        return 0


def split_audio(audio_path, chunk_seconds=CHUNK_DURATION):
    """Split audio into chunks, return list of chunk paths."""
    duration = get_duration(audio_path)
    if duration <= 0:
        return []

    chunk_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    chunk_dir.mkdir(exist_ok=True)

    chunks = []
    for i, start in enumerate(range(0, int(duration), chunk_seconds)):
        chunk_path = chunk_dir / f"chunk_{i:03d}.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(audio_path),
             "-ss", str(start), "-t", str(chunk_seconds),
             "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000",
             str(chunk_path)],
            capture_output=True, timeout=120
        )
        if chunk_path.exists():
            chunks.append(chunk_path)

    return chunks


def transcribe(audio_path, prompt):
    """Transcribe a single audio file using the already-loaded model, with timeout."""
    # Set alarm for timeout
    signal.alarm(FILE_TIMEOUT)
    try:
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=MODEL,
            initial_prompt=prompt,
            language="en",
            verbose=False,
        )
        return result["text"]
    finally:
        signal.alarm(0)  # Cancel alarm


def cleanup_chunks(audio_path):
    """Clean up any chunk directory for this file."""
    chunk_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    if chunk_dir.exists():
        for f in chunk_dir.iterdir():
            f.unlink(missing_ok=True)
        try:
            chunk_dir.rmdir()
        except OSError:
            pass


def process_file(audio_path, prompt):
    """Transcribe file, handling long files via chunking. Model stays loaded."""
    audio_path = Path(audio_path)
    duration = get_duration(audio_path)

    if duration > CHUNK_THRESHOLD:
        # Long file — chunk and transcribe each piece
        chunks = split_audio(audio_path)
        if not chunks:
            return None

        texts = []
        for chunk in chunks:
            try:
                text = transcribe(chunk, prompt)
                texts.append(text)
            except TranscriptionTimeout:
                # Skip this chunk but continue with others
                texts.append("")
            finally:
                chunk.unlink(missing_ok=True)

        cleanup_chunks(audio_path)
        combined = " ".join(t for t in texts if t)
        return correct_transcript(combined) if combined.strip() else None
    else:
        # Short/medium file — transcribe directly
        text = transcribe(audio_path, prompt)
        return correct_transcript(text)


def main():
    # Set up timeout signal handler
    signal.signal(signal.SIGALRM, timeout_handler)

    prompt = get_whisper_prompt()

    # Warm up — first call loads the model into Metal GPU memory
    print("LOADING", flush=True)

    # Read file paths from stdin, one per line
    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue

        try:
            audio_path = Path(path)
            if not audio_path.exists():
                print(f"FAIL {path} File not found", flush=True)
                continue

            transcript = process_file(audio_path, prompt)

            if transcript:
                txt = audio_path.with_suffix('.txt')
                txt.write_text(transcript, encoding='utf-8')
                # Delete audio after successful transcription
                audio_path.unlink(missing_ok=True)
                print(f"OK {path}", flush=True)
            else:
                print(f"FAIL {path} No transcript produced", flush=True)

        except TranscriptionTimeout:
            cleanup_chunks(Path(path))
            print(f"FAIL {path} Timeout (>{FILE_TIMEOUT//60} min)", flush=True)
        except Exception as e:
            cleanup_chunks(Path(path))
            print(f"FAIL {path} {str(e)[:200]}", flush=True)


if __name__ == "__main__":
    main()
