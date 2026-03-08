#!/usr/bin/env python3
"""
Parallel Whisper Transcription — Forged by Freedom
Runs N parallel MLX Whisper workers to transcribe pending audio files.
Prioritizes channels by tier (ThinkBig first, then PED experts, etc.)

Usage:
    python3 transcribe_parallel.py              # 3 workers (default for 16GB)
    python3 transcribe_parallel.py --workers 2  # Custom worker count
    python3 transcribe_parallel.py --channel @ThinkBIGBodybuilding  # Single channel
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"

# Channel priority tiers — lower number = transcribed first
TIER1 = [  # Priority 0 — your core sources
    "@ThinkBIGBodybuilding", "@rxmuscle", "@anabolicbodybuilding",
    "@realtattered", "@TannerTatteredFAQ", "@johnjewett3", "@J3University",
]
TIER2 = [  # Priority 1 — key PED/fitness experts
    "@AnabolicDoc", "@MorePlatesMoreDates", "@vigoroussteve",
    "@LeoandLongevity", "@GregDoucette", "@hubermanlab",
    "@PeterAttiaMD", "@FoundMyFitness", "@DrGabrielleLyon",
    "@JeffNippard", "@RenaissancePeriodization", "@Biolayne",
    "@AthleanX", "@BarbellMedicine",
]
TIER3 = [  # Priority 2 — female health experts
    "@DrStacySims", "@drmaryclairehaver", "@DrMindyPelz",
    "@HollyBaxter", "@SoheeFit", "@LaurinConlin", "@megsquats",
    "@AshleyKaltwasser", "@ErinSternFitness", "@JulieLohre",
    "@KristyHawkins", "@StephanieButtermore",
]


def get_priority(channel_name):
    """Return priority number for sorting (lower = first)."""
    if channel_name in TIER1:
        return 0
    if channel_name in TIER2:
        return 1
    if channel_name in TIER3:
        return 2
    return 3


def find_pending(only_channel=None):
    """Find all audio files without matching transcripts, sorted by priority."""
    pending = []
    extensions = {'.mp3', '.m4a', '.wav', '.opus', '.webm'}

    search_dir = CHANNELS_DIR / only_channel if only_channel else CHANNELS_DIR

    for audio in search_dir.rglob("*"):
        if audio.suffix.lower() not in extensions:
            continue
        if audio.parent.name.endswith("_chunks"):
            continue  # Skip chunk directories

        txt = audio.with_suffix('.txt')
        if not txt.exists():
            channel = audio.parent.name
            priority = get_priority(channel)
            pending.append((priority, channel, audio))

    # Sort by priority, then channel name, then filename
    pending.sort(key=lambda x: (x[0], x[1], x[2].name))
    return pending


def get_audio_duration(audio_path):
    """Get duration of audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception:
        return 0


def split_and_transcribe(audio_path, chunk_seconds=600):
    """Split long audio into chunks, transcribe each, concatenate results."""
    chunk_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    chunk_dir.mkdir(exist_ok=True)

    # Get duration
    duration = get_audio_duration(audio_path)
    if duration <= 0:
        return None

    # Split into chunks
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

    if not chunks:
        return None

    # Transcribe each chunk
    full_text = []
    for chunk in chunks:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "whisper_transcribe.py"), str(chunk)],
            capture_output=True, text=True, timeout=1800
        )
        txt = chunk.with_suffix('.txt')
        if txt.exists():
            full_text.append(txt.read_text(encoding='utf-8'))
            txt.unlink()
        chunk.unlink(missing_ok=True)

    # Cleanup chunk directory
    try:
        chunk_dir.rmdir()
    except OSError:
        pass

    return " ".join(full_text) if full_text else None


def transcribe_one(audio_path):
    """Transcribe a single audio file. Auto-chunks files >20 min. Returns (path, success, error)."""
    try:
        duration = get_audio_duration(audio_path)

        # For long files (>20 min), split into 10-min chunks first
        if duration > 1200:
            transcript = split_and_transcribe(audio_path, chunk_seconds=600)
            if transcript:
                txt = audio_path.with_suffix('.txt')
                txt.write_text(transcript, encoding='utf-8')
                try:
                    audio_path.unlink()
                except OSError:
                    pass
                return (str(audio_path), True, None)
            else:
                return (str(audio_path), False, f"Chunked transcription failed ({duration/60:.0f} min file)")

        # Normal files — direct transcription
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "whisper_transcribe.py"), str(audio_path)],
            capture_output=True, text=True, timeout=1800  # 30 min max per file
        )

        txt = audio_path.with_suffix('.txt')
        if txt.exists():
            # Delete audio after successful transcription
            try:
                audio_path.unlink()
            except OSError:
                pass
            return (str(audio_path), True, None)
        else:
            return (str(audio_path), False, result.stderr[-500:] if result.stderr else "No transcript produced")

    except subprocess.TimeoutExpired:
        return (str(audio_path), False, f"Timeout (>30 min, {duration/60:.0f} min file)")
    except Exception as e:
        return (str(audio_path), False, str(e))


def main():
    parser = argparse.ArgumentParser(description="Parallel Whisper transcription")
    parser.add_argument("--workers", "-w", type=int, default=3,
                        help="Number of parallel workers (default: 3 for 16GB Mac)")
    parser.add_argument("--channel", "-c", type=str, default=None,
                        help="Only transcribe a specific channel (e.g. @ThinkBIGBodybuilding)")
    parser.add_argument("--limit", "-l", type=int, default=0,
                        help="Max files to transcribe (0 = unlimited)")
    args = parser.parse_args()

    pending = find_pending(args.channel)
    if not pending:
        print("No pending audio files to transcribe.")
        return

    if args.limit > 0:
        pending = pending[:args.limit]

    total = len(pending)
    workers = min(args.workers, total)

    # Show what we're about to do
    print(f"{'='*60}")
    print(f"PARALLEL WHISPER TRANSCRIPTION")
    print(f"{'='*60}")
    print(f"Pending files: {total}")
    print(f"Workers: {workers}")
    print(f"Model: mlx-community/whisper-large-v3-turbo")
    print(f"Cost: FREE (local Apple Silicon)")
    print()

    # Show breakdown by priority tier
    tiers = {}
    for pri, ch, _ in pending:
        tier_label = ["PRIORITY", "HIGH", "FEMALE", "OTHER"][pri]
        tiers[tier_label] = tiers.get(tier_label, 0) + 1
    for tier, count in tiers.items():
        print(f"  {tier}: {count} files")

    # Show breakdown by channel (top 15)
    channels = {}
    for _, ch, _ in pending:
        channels[ch] = channels.get(ch, 0) + 1
    print()
    print("Top channels:")
    for ch, count in sorted(channels.items(), key=lambda x: -x[1])[:15]:
        pri = get_priority(ch)
        tier = ["PRI", "HIGH", "FEM", "MID"][pri]
        print(f"  [{tier}] {count:3d}  {ch}")
    print()
    print(f"Starting transcription with {workers} workers...")
    print(f"{'='*60}")

    completed = 0
    failed = 0
    start_time = time.time()

    audio_paths = [audio for _, _, audio in pending]

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(transcribe_one, path): path for path in audio_paths}

        for future in as_completed(futures):
            path_str, success, error = future.result()
            completed += 1
            elapsed = time.time() - start_time
            rate = completed / (elapsed / 60) if elapsed > 0 else 0

            filename = Path(path_str).name
            channel = Path(path_str).parent.name

            if success:
                print(f"[{completed}/{total}] OK  {channel}/{filename[:50]}  ({rate:.1f}/min)")
            else:
                failed += 1
                print(f"[{completed}/{total}] FAIL {channel}/{filename[:50]} — {error[:80] if error else 'unknown'}")

    elapsed = time.time() - start_time
    print()
    print(f"{'='*60}")
    print(f"DONE in {elapsed/60:.1f} minutes")
    print(f"Transcribed: {completed - failed}/{total}")
    if failed:
        print(f"Failed: {failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
