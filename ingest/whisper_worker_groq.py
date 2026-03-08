#!/usr/bin/env python3
"""
Groq Whisper Worker — Forged by Freedom
========================================
Uses Groq's free cloud API for Whisper transcription.
Zero local RAM usage — all processing happens on Groq's servers.

Protocol (stdin/stdout) — same as whisper_worker.py:
    IN:  /path/to/audio.mp3
    OUT: OK /path/to/audio.mp3
    OUT: FAIL /path/to/audio.mp3 error message

Handles:
- Files up to 25MB directly
- Larger files get split into 25MB chunks via ffmpeg
- Rate limiting with automatic backoff
- Retries on transient errors

Usage:
    echo "/path/to/file.mp3" | GROQ_API_KEY=xxx python3 whisper_worker_groq.py
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import mimetypes

sys.path.insert(0, str(Path(__file__).parent))
from anabolics_vocabulary import get_whisper_prompt, correct_transcript

GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"
MAX_FILE_SIZE = 24 * 1024 * 1024  # 24MB (under 25MB limit)
CHUNK_DURATION = 1200             # 20-min chunks (stay under 25MB at 64kbps)
MAX_RETRIES = 5
BASE_WAIT = 10                    # Base wait time for rate limits


def get_api_key():
    """Get Groq API key from env or .env file."""
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key

    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    return None


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
    """Split audio into chunks that fit under the API size limit."""
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
        if chunk_path.exists() and chunk_path.stat().st_size > 0:
            chunks.append(chunk_path)

    return chunks


def cleanup_chunks(audio_path):
    """Clean up chunk directory."""
    chunk_dir = Path(audio_path).parent / f"{Path(audio_path).stem}_chunks"
    if chunk_dir.exists():
        for f in chunk_dir.iterdir():
            f.unlink(missing_ok=True)
        try:
            chunk_dir.rmdir()
        except OSError:
            pass


def transcribe_via_groq(audio_path, api_key, prompt):
    """Transcribe a single audio file via Groq API with retry logic."""
    audio_path = Path(audio_path)

    for attempt in range(MAX_RETRIES):
        try:
            # Build multipart form data manually
            boundary = "----FormBoundary" + str(int(time.time() * 1000))
            body = b""

            # Add file field
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'.encode()
            body += b"Content-Type: audio/mpeg\r\n\r\n"
            body += audio_path.read_bytes()
            body += b"\r\n"

            # Add model field
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="model"\r\n\r\n'
            body += MODEL.encode()
            body += b"\r\n"

            # Add language field
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="language"\r\n\r\n'
            body += b"en\r\n"

            # Add prompt field
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="prompt"\r\n\r\n'
            body += prompt.encode()
            body += b"\r\n"

            # Add response format
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="response_format"\r\n\r\n'
            body += b"text\r\n"

            body += f"--{boundary}--\r\n".encode()

            req = Request(
                GROQ_API_URL,
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                method="POST",
            )

            with urlopen(req, timeout=300) as resp:
                return resp.read().decode("utf-8").strip()

        except HTTPError as e:
            if e.code == 429:
                # Rate limited — wait and retry
                retry_after = int(e.headers.get("retry-after", BASE_WAIT * (attempt + 1)))
                wait = max(retry_after, BASE_WAIT)
                sys.stderr.write(f"Rate limited, waiting {wait}s (attempt {attempt+1})...\n")
                sys.stderr.flush()
                time.sleep(wait)
            elif e.code >= 500:
                # Server error — retry with backoff
                wait = BASE_WAIT * (attempt + 1)
                sys.stderr.write(f"Server error {e.code}, retrying in {wait}s...\n")
                sys.stderr.flush()
                time.sleep(wait)
            else:
                error_body = e.read().decode("utf-8", errors="replace")[:300]
                raise Exception(f"HTTP {e.code}: {error_body}")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = BASE_WAIT * (attempt + 1)
                sys.stderr.write(f"Error: {e}, retrying in {wait}s...\n")
                sys.stderr.flush()
                time.sleep(wait)
            else:
                raise

    raise Exception(f"Failed after {MAX_RETRIES} retries")


def process_file(audio_path, api_key, prompt):
    """Transcribe a file, handling large files via chunking."""
    audio_path = Path(audio_path)
    file_size = audio_path.stat().st_size

    if file_size > MAX_FILE_SIZE:
        # Large file — split into chunks
        chunks = split_audio(audio_path)
        if not chunks:
            return None

        texts = []
        for chunk in chunks:
            try:
                text = transcribe_via_groq(chunk, api_key, prompt)
                texts.append(text)
            except Exception as e:
                sys.stderr.write(f"Chunk failed: {e}\n")
                sys.stderr.flush()
            finally:
                chunk.unlink(missing_ok=True)

        cleanup_chunks(audio_path)
        combined = " ".join(t for t in texts if t)
        return correct_transcript(combined) if combined.strip() else None
    else:
        # Normal file — transcribe directly
        text = transcribe_via_groq(audio_path, api_key, prompt)
        return correct_transcript(text)


def main():
    api_key = get_api_key()
    if not api_key:
        print("FAIL NO_KEY GROQ_API_KEY not found in env or .env", flush=True)
        sys.exit(1)

    prompt = get_whisper_prompt()

    print("LOADING", flush=True)

    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue

        try:
            audio_path = Path(path)
            if not audio_path.exists():
                print(f"FAIL {path} File not found", flush=True)
                continue

            transcript = process_file(audio_path, api_key, prompt)

            if transcript:
                txt = audio_path.with_suffix('.txt')
                txt.write_text(transcript, encoding='utf-8')
                audio_path.unlink(missing_ok=True)
                print(f"OK {path}", flush=True)
            else:
                print(f"FAIL {path} No transcript produced", flush=True)

        except Exception as e:
            cleanup_chunks(Path(path))
            print(f"FAIL {path} {str(e)[:200]}", flush=True)


if __name__ == "__main__":
    main()
