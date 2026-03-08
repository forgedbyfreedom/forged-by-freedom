#!/usr/bin/env python3
"""
Forged by Freedom — Continuous Pipeline Daemon
===============================================
Runs continuously: transcribe → fix vocab → ingest → download → repeat

Priority: Transcription > Ingestion > Downloads

Architecture:
- Transcription: Persistent whisper_worker.py process (loads model ONCE)
- Downloads: 1 background yt-dlp process (network-bound)
- Ingestion: Runs in batches after every N transcriptions complete
- Vocab fix: Runs before each ingestion batch

Usage:
    python3 pipeline_daemon.py                  # Run forever
    python3 pipeline_daemon.py --once           # Single pass then exit
    python3 pipeline_daemon.py --no-download    # Transcribe + ingest only
"""

import os
import sys
import time
import signal
import argparse
import subprocess
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"
LOG_DIR = BASE_DIR / "logs"
STATE_FILE = BASE_DIR / ".daemon_state.json"

# Ensure log directory exists
LOG_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(BASE_DIR))

# ─── Configuration ────────────────────────────────────────────
INGEST_BATCH_SIZE = 50          # Ingest to Pinecone every N transcriptions
SLEEP_BETWEEN_CYCLES = 300      # 5 min between full cycles

# Channel priority tiers
TIER1 = [
    "@ThinkBIGBodybuilding", "@rxmuscle", "@anabolicbodybuilding",
    "@realtattered", "@TannerTatteredFAQ", "@johnjewett3", "@J3University",
]
TIER2 = [
    "@AnabolicDoc", "@MorePlatesMoreDates", "@vigoroussteve",
    "@LeoandLongevity", "@GregDoucette", "@hubermanlab",
    "@PeterAttiaMD", "@FoundMyFitness", "@DrGabrielleLyon",
    "@JeffNippard", "@RenaissancePeriodization", "@Biolayne",
    "@AthleanX", "@BarbellMedicine",
]
TIER3 = [
    "@DrStacySims", "@drmaryclairehaver", "@DrMindyPelz",
    "@HollyBaxter", "@SoheeFit", "@LaurinConlin", "@megsquats",
    "@AshleyKaltwasser", "@ErinSternFitness", "@JulieLohre",
    "@KristyHawkins", "@StephanieButtermore",
]
SKIP_CHANNELS = [
    "@3Blue1Brown", "@kurzgesagt", "@veritasium", "@Vsauce",
    "@numberphile", "@minutephysics", "@MulliganBrothers", "@BroScienceLife",
]

# ─── Logging ──────────────────────────────────────────────────
def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line, flush=True)


def header(msg):
    log("")
    log("=" * 60)
    log(f"  {msg}")
    log("=" * 60)


# ─── State Management ────────────────────────────────────────
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"total_transcribed": 0, "total_ingested": 0, "total_downloaded": 0,
            "since_last_ingest": 0, "last_run": None, "channels_ingested": []}


def save_state(state):
    state["last_run"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ─── Priority Sorting ────────────────────────────────────────
def get_priority(channel_name):
    if channel_name in TIER1: return 0
    if channel_name in TIER2: return 1
    if channel_name in TIER3: return 2
    if channel_name in SKIP_CHANNELS: return 99
    return 3


def get_audio_duration(audio_path):
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


# ─── Find Pending Work ───────────────────────────────────────
def find_pending_transcriptions(probe_durations=False):
    """Find audio files without matching transcripts, sorted by priority.
    If probe_durations=True, also gets duration for sorting short-first (slower startup)."""
    pending = []
    extensions = {'.mp3', '.m4a', '.wav', '.opus'}

    for audio in CHANNELS_DIR.rglob("*"):
        if audio.suffix.lower() not in extensions:
            continue
        if audio.parent.name.endswith("_chunks"):
            continue
        channel = audio.parent.name
        if channel in SKIP_CHANNELS:
            continue

        txt = audio.with_suffix('.txt')
        if not txt.exists():
            priority = get_priority(channel)
            # Use file size as proxy for duration (avoids 1200+ ffprobe calls)
            size = audio.stat().st_size if audio.exists() else 0
            pending.append((priority, size, channel, audio))

    # Sort by priority first, then file size (small=short first), then name
    pending.sort(key=lambda x: (x[0], x[1], x[3].name))
    return pending


def find_channels_needing_ingest(state):
    """Find channels with new transcripts."""
    channels_with_new = set()
    for txt in CHANNELS_DIR.rglob("*.txt"):
        if txt.name.startswith("master_"):
            continue
        channel = txt.parent.name
        if channel.startswith("@"):
            channels_with_new.add(channel)
    return list(channels_with_new)


# ─── Persistent Worker Transcription ────────────────────────
def start_worker():
    """Start the persistent whisper worker process."""
    worker_script = BASE_DIR / "whisper_worker.py"
    proc = subprocess.Popen(
        [sys.executable, "-u", str(worker_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # Discard stderr — prevents pipe buffer deadlock
        text=True,
        bufsize=1,  # Line-buffered
    )

    # Wait for LOADING message
    first_line = proc.stdout.readline().strip()
    if first_line == "LOADING":
        log("Worker started, model loading...")
    else:
        log(f"Worker unexpected output: {first_line}", "WARN")

    return proc


WORKER_TIMEOUT = 600  # 10 min max per file


def send_to_worker(proc, audio_path):
    """Send a file path to the worker and get the result, with timeout."""
    import select

    try:
        proc.stdin.write(str(audio_path) + "\n")
        proc.stdin.flush()

        # Wait for result with timeout (prevents infinite hang)
        ready, _, _ = select.select([proc.stdout], [], [], WORKER_TIMEOUT)

        if not ready:
            # Worker timed out — kill and signal restart needed
            return (str(audio_path), False, f"Daemon timeout (>{WORKER_TIMEOUT//60} min)")

        result_line = proc.stdout.readline().strip()

        if result_line.startswith("OK "):
            return (str(audio_path), True, None)
        elif result_line.startswith("FAIL "):
            parts = result_line.split(" ", 2)
            error = parts[2] if len(parts) > 2 else "Unknown error"
            return (str(audio_path), False, error)
        elif result_line == "":
            return (str(audio_path), False, "Worker process died")
        else:
            return (str(audio_path), False, f"Unexpected: {result_line[:100]}")

    except (BrokenPipeError, OSError) as e:
        return (str(audio_path), False, f"Worker pipe error: {e}")


def run_transcription_batch(pending, state, worker_proc):
    """Transcribe a batch of files using the persistent worker."""
    if not pending:
        return 0, worker_proc

    total = len(pending)

    header(f"TRANSCRIBING {total} FILES (persistent worker)")

    # Show tier breakdown
    tiers = {}
    for pri, dur, ch, _ in pending:
        label = ["PRIORITY", "HIGH", "FEMALE", "OTHER"][min(pri, 3)]
        tiers[label] = tiers.get(label, 0) + 1
    for tier, count in tiers.items():
        log(f"  {tier}: {count}")

    # Show size stats (file size as proxy for duration: 64kbps mp3 = ~480KB/min)
    sizes = [sz for _, sz, _, _ in pending]
    small = sum(1 for s in sizes if s < 10_000_000)      # <10MB (~20 min)
    medium_f = sum(1 for s in sizes if 10_000_000 <= s < 30_000_000)  # 10-30MB
    large_f = sum(1 for s in sizes if s >= 30_000_000)    # >30MB (~60+ min)
    log(f"  Small (<10MB): {small}, Medium (10-30MB): {medium_f}, Large (>30MB): {large_f}")

    completed = 0
    failed = 0
    start_time = time.time()
    channels_touched = set()
    new_transcripts = []  # Track newly created .txt files for vocab fix

    for _, sz, ch, audio in pending:
        # Check if worker is still alive
        if worker_proc.poll() is not None:
            log("Worker died, restarting...", "WARN")
            worker_proc = start_worker()
            # First file after restart will trigger model load
            log("Worker restarted, model reloading (one-time cost)...")
            # Send a warmup — the first transcribe() call loads the model
            # The worker handles this transparently

        size_mb = sz / 1_000_000
        log(f"[{completed+1}/{total}] Starting {ch}/{audio.stem[:40]}... ({size_mb:.0f}MB)")

        path_str, success, error = send_to_worker(worker_proc, audio)
        completed += 1
        elapsed = time.time() - start_time
        rate = completed / (elapsed / 60) if elapsed > 0 else 0

        p = Path(path_str)
        channel = p.parent.name
        channels_touched.add(channel)

        if success:
            state["total_transcribed"] += 1
            state["since_last_ingest"] += 1
            new_transcripts.append(p.with_suffix('.txt'))
            log(f"[{completed}/{total}] OK  {channel}/{p.stem[:45]}  ({rate:.1f}/min)")
        else:
            failed += 1
            log(f"[{completed}/{total}] FAIL {channel}/{p.stem[:45]} — {error[:80]}", "WARN")

            # If worker timed out or died, restart it
            if "timeout" in (error or "").lower() or "died" in (error or "").lower() or "pipe" in (error or "").lower():
                log("Restarting worker after failure...", "WARN")
                try:
                    worker_proc.kill()
                    worker_proc.wait(timeout=5)
                except Exception:
                    pass
                worker_proc = start_worker()

        # Save state periodically
        if completed % 5 == 0:
            save_state(state)

    elapsed = time.time() - start_time
    log(f"Batch done: {completed-failed}/{total} in {elapsed/60:.1f}min ({rate:.1f}/min)")

    save_state(state)
    return completed - failed, worker_proc, new_transcripts


# ─── Vocab Fix + Build Masters + Ingest ──────────────────────
def run_vocab_fix(transcript_files=None):
    """Run vocabulary corrections on new transcripts only (or all if no list given)."""
    header("VOCABULARY CORRECTIONS")

    if transcript_files:
        # Fast path: only fix the newly created files
        from anabolics_vocabulary import correct_transcript
        fixed = 0
        for txt_path in transcript_files:
            try:
                if not txt_path.exists():
                    continue
                original = txt_path.read_text(encoding='utf-8', errors='ignore')
                corrected = correct_transcript(original)
                if original != corrected:
                    txt_path.write_text(corrected, encoding='utf-8')
                    fixed += 1
            except Exception as e:
                log(f"Vocab fix error on {txt_path.name}: {e}", "WARN")
        log(f"Vocab fix complete — {fixed}/{len(transcript_files)} files corrected")
    else:
        # Fallback: run on all files
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "fix_transcripts.py")],
            capture_output=True, text=True, timeout=3600
        )
        if result.returncode == 0:
            log("Vocab fix complete (full scan)")
        else:
            log(f"Vocab fix error: {result.stderr[-200:]}", "WARN")


def run_build_masters():
    """Rebuild master transcripts."""
    header("BUILD MASTER TRANSCRIPTS")
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "build_master_transcripts.py")],
        capture_output=True, text=True, timeout=1800
    )
    if result.returncode == 0:
        log("Masters rebuilt")
    else:
        log(f"Masters error: {result.stderr[-200:]}", "WARN")


def run_ingest(channels=None):
    """Ingest to Pinecone."""
    header("PINECONE INGEST")
    cmd = [sys.executable, str(BASE_DIR / "ingest_to_pinecone.py")]
    if channels:
        cmd.extend(["--channels"] + list(channels))

    log(f"Ingesting {len(channels) if channels else 'ALL'} channels...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    for line in result.stdout.split('\n'):
        if 'INGEST COMPLETE' in line or 'Episodes:' in line or 'Chunks:' in line or 'Words:' in line:
            log(line.strip())

    if result.returncode != 0:
        log(f"Ingest error: {result.stderr[-200:]}", "WARN")


def run_fix_and_ingest(channels_to_ingest, state, new_transcripts=None):
    """Run full post-transcription pipeline: fix vocab → build masters → ingest."""
    if not channels_to_ingest:
        return

    run_vocab_fix(new_transcripts)
    run_build_masters()

    batch_size = 10
    channel_list = list(channels_to_ingest)
    for i in range(0, len(channel_list), batch_size):
        batch = channel_list[i:i+batch_size]
        run_ingest(batch)

    state["since_last_ingest"] = 0
    state["total_ingested"] += len(channels_to_ingest)
    save_state(state)


# ─── Downloads ────────────────────────────────────────────────
def run_downloads():
    """Download new videos from YouTube channels."""
    header("DOWNLOADING NEW CONTENT")

    yt_dlp = os.path.expanduser("~/Library/Python/3.12/bin/yt-dlp")
    if not os.path.exists(yt_dlp):
        yt_dlp = "yt-dlp"

    url_files = sorted(CHANNELS_DIR.glob("*/channel.url"))
    downloaded = 0

    prioritized = []
    for url_file in url_files:
        channel = url_file.parent.name
        if channel in SKIP_CHANNELS:
            continue
        priority = get_priority(channel)
        prioritized.append((priority, channel, url_file))
    prioritized.sort()

    for priority, channel, url_file in prioritized:
        url = url_file.read_text().strip()
        if not url:
            continue

        if priority == 0:
            max_dl = 50
        elif priority == 1:
            max_dl = 30
        elif priority == 2:
            max_dl = 20
        else:
            max_dl = 10

        tier_label = ["PRI", "HIGH", "FEM", "MID"][min(priority, 3)]
        channel_dir = url_file.parent

        existing = len(list(channel_dir.glob("*.txt"))) + len(list(channel_dir.glob("*.mp3")))
        if existing >= max_dl:
            continue

        remaining = max_dl - existing
        if remaining <= 0:
            continue

        log(f"[{tier_label}] Downloading up to {remaining} from {channel}...")

        cmd = [
            yt_dlp,
            "-x", "--audio-format", "mp3", "--audio-quality", "64K",
            "--max-downloads", str(remaining),
            "--download-archive", str(channel_dir / ".downloaded"),
            "--no-overwrites",
            "--extractor-args", "youtubetab:skip=authcheck",
            "--cookies-from-browser", "chrome",
            "--sleep-interval", "3", "--max-sleep-interval", "8",
            "-o", str(channel_dir / "%(title)s [%(id)s].%(ext)s"),
            url
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            new_mp3s = len([f for f in channel_dir.glob("*.mp3")
                           if not f.with_suffix('.txt').exists()])
            if new_mp3s > 0:
                downloaded += new_mp3s
                log(f"  Got {new_mp3s} new audio files from {channel}")
        except subprocess.TimeoutExpired:
            log(f"  Download timeout for {channel}", "WARN")
        except Exception as e:
            log(f"  Download error for {channel}: {e}", "WARN")

    log(f"Downloads complete: {downloaded} new files")
    return downloaded


# ─── Main Loop ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Forged by Freedom Pipeline Daemon")
    parser.add_argument("--once", action="store_true", help="Single pass then exit")
    parser.add_argument("--no-download", action="store_true", help="Skip downloads")
    parser.add_argument("--no-ingest", action="store_true", help="Skip Pinecone ingest")
    args = parser.parse_args()

    state = load_state()
    cycle = 0

    header("FORGED BY FREEDOM PIPELINE DAEMON v3")
    log("Architecture: Persistent worker (whisper-small)")
    log(f"Ingest every: {INGEST_BATCH_SIZE} transcriptions")
    log(f"Downloads: {'disabled' if args.no_download else 'enabled'}")
    log(f"Mode: {'single pass' if args.once else 'continuous'}")
    log(f"State: {state['total_transcribed']} transcribed, {state['total_ingested']} ingested")

    # Start the persistent whisper worker
    log("Starting persistent whisper worker...")
    worker_proc = start_worker()

    # Warm up the model with first transcription (will be slow, then all subsequent are fast)
    log("Model will load on first file (one-time ~30s cost)")

    # Graceful shutdown
    running = [True]
    def shutdown(sig, frame):
        log("Shutdown signal received, finishing current file...")
        running[0] = False
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while running[0]:
        cycle += 1
        header(f"CYCLE {cycle} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        # ─── Phase 1: Transcribe pending audio ────────────────
        pending = find_pending_transcriptions()
        channels_touched = set()

        if pending:
            log(f"Found {len(pending)} files to transcribe")

            # Process in batches to allow periodic ingestion
            batch_start = 0
            all_new_transcripts = []
            while batch_start < len(pending) and running[0]:
                batch_end = min(batch_start + INGEST_BATCH_SIZE, len(pending))
                batch = pending[batch_start:batch_end]

                for _, _, ch, _ in batch:
                    channels_touched.add(ch)

                transcribed, worker_proc, new_transcripts = run_transcription_batch(batch, state, worker_proc)
                all_new_transcripts.extend(new_transcripts)

                if not args.no_ingest and state["since_last_ingest"] >= INGEST_BATCH_SIZE:
                    # Kill worker during ingest to free memory
                    log("Pausing worker for ingest...")
                    worker_proc.stdin.close()
                    worker_proc.wait(timeout=10)

                    run_fix_and_ingest(channels_touched, state, all_new_transcripts)
                    channels_touched = set()
                    all_new_transcripts = []

                    # Restart worker
                    log("Restarting worker...")
                    worker_proc = start_worker()

                batch_start = batch_end

            # Final ingest for any remaining
            if not args.no_ingest and channels_touched and state["since_last_ingest"] > 0:
                worker_proc.stdin.close()
                worker_proc.wait(timeout=10)
                run_fix_and_ingest(channels_touched, state, all_new_transcripts)
                worker_proc = start_worker()
        else:
            log("No pending transcriptions")

        # ─── Phase 2: Download new content ────────────────────
        if not args.no_download and running[0]:
            # Kill worker during downloads to free memory
            log("Pausing worker for downloads...")
            try:
                worker_proc.stdin.close()
                worker_proc.wait(timeout=10)
            except Exception:
                pass

            new_downloads = run_downloads()

            # Restart worker if we have new files
            if new_downloads > 0:
                worker_proc = start_worker()
                new_pending = find_pending_transcriptions()
                if new_pending:
                    channels_touched = set()
                    for _, _, ch, _ in new_pending:
                        channels_touched.add(ch)
                    transcribed, worker_proc, new_transcripts = run_transcription_batch(new_pending, state, worker_proc)
                    if not args.no_ingest and channels_touched:
                        worker_proc.stdin.close()
                        worker_proc.wait(timeout=10)
                        run_fix_and_ingest(channels_touched, state, new_transcripts)
                        worker_proc = start_worker()
            else:
                worker_proc = start_worker()

        # ─── Status Report ────────────────────────────────────
        header("CYCLE COMPLETE")
        log(f"Total transcribed: {state['total_transcribed']}")
        log(f"Total ingested: {state['total_ingested']}")
        remaining = find_pending_transcriptions()
        log(f"Remaining to transcribe: {len(remaining)}")
        save_state(state)

        if args.once:
            log("Single pass mode — exiting")
            break

        if not remaining and args.no_download:
            log("Nothing left to do — exiting")
            break

        if running[0]:
            log(f"Sleeping {SLEEP_BETWEEN_CYCLES//60} minutes before next cycle...")
            for _ in range(SLEEP_BETWEEN_CYCLES):
                if not running[0]:
                    break
                time.sleep(1)

    # Cleanup worker
    try:
        worker_proc.stdin.close()
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
    except Exception:
        pass

    header("DAEMON STOPPED")
    log(f"Final stats: {state['total_transcribed']} transcribed, {state['total_ingested']} ingested")
    save_state(state)


if __name__ == "__main__":
    main()
