#!/usr/bin/env python3
"""
Transcribe audio/video files using OpenAI Whisper with
domain-specific prompting for anabolics/fitness vocabulary.

Usage:
    python whisper_transcribe.py video.mp4                    # Single file
    python whisper_transcribe.py --channel @ChannelName       # Transcribe channel
    python whisper_transcribe.py --url "youtube_url" --out .  # Download + transcribe

Requirements:
    pip install openai yt-dlp
"""

import os
import sys
import argparse
import tempfile
import subprocess
from pathlib import Path
from openai import OpenAI
from anabolics_vocabulary import get_whisper_prompt, correct_transcript

# Max file size for Whisper API (25MB)
MAX_FILE_SIZE = 25 * 1024 * 1024


def get_client():
    """Get OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        sys.exit(1)
    return OpenAI(api_key=api_key)


def extract_audio(video_path, output_path=None):
    """Extract audio from video file using ffmpeg."""
    if output_path is None:
        output_path = video_path.with_suffix('.mp3')

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn",  # No video
        "-acodec", "libmp3lame",
        "-ab", "64k",  # Low bitrate to reduce file size
        "-ar", "16000",  # 16kHz sample rate (Whisper optimal)
        str(output_path)
    ]

    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def split_audio(audio_path, chunk_duration=600):
    """Split audio into chunks for large files."""
    chunks = []
    output_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    output_dir.mkdir(exist_ok=True)

    # Get duration
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())

    # Split into chunks
    for i, start in enumerate(range(0, int(duration), chunk_duration)):
        chunk_path = output_dir / f"chunk_{i:03d}.mp3"
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-ss", str(start), "-t", str(chunk_duration),
            "-acodec", "libmp3lame", "-ab", "64k",
            str(chunk_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        chunks.append(chunk_path)

    return chunks


def transcribe_audio(client, audio_path):
    """Transcribe audio file using Whisper with domain prompting."""
    prompt = get_whisper_prompt()

    file_size = os.path.getsize(audio_path)

    if file_size > MAX_FILE_SIZE:
        print(f"  ⚠️  File too large ({file_size / 1024 / 1024:.1f}MB), splitting...")
        chunks = split_audio(audio_path)
        transcripts = []

        for i, chunk in enumerate(chunks):
            print(f"  📝 Transcribing chunk {i + 1}/{len(chunks)}...")
            with open(chunk, "rb") as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    prompt=prompt,
                    language="en"
                )
            transcripts.append(response.text)
            os.remove(chunk)  # Clean up chunk

        # Clean up chunks directory
        chunks[0].parent.rmdir()

        return " ".join(transcripts)

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            prompt=prompt,
            language="en"
        )

    return response.text


def download_youtube(url, output_dir):
    """Download YouTube video audio."""
    output_template = str(output_dir / "%(title)s [%(id)s].%(ext)s")

    cmd = [
        "yt-dlp",
        "-x",  # Extract audio
        "--audio-format", "mp3",
        "--audio-quality", "64K",
        "-o", output_template,
        url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Find the downloaded file
    for f in output_dir.glob("*.mp3"):
        return f

    print(f"❌ Download failed: {result.stderr}")
    return None


def process_file(client, input_path, output_path=None):
    """Process a single video/audio file."""
    input_path = Path(input_path)

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return

    print(f"🎬 Processing: {input_path.name}")

    # Determine if we need to extract audio
    audio_path = input_path
    temp_audio = None

    if input_path.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
        print("  🔊 Extracting audio...")
        temp_audio = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        audio_path = extract_audio(input_path, Path(temp_audio.name))

    # Transcribe
    print("  🎤 Transcribing with Whisper...")
    transcript = transcribe_audio(client, audio_path)

    # Apply post-processing corrections
    print("  🔧 Applying vocabulary corrections...")
    transcript = correct_transcript(transcript)

    # Save transcript
    if output_path is None:
        output_path = input_path.with_suffix('.txt')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(transcript)

    print(f"  ✅ Saved: {output_path}")

    # Cleanup
    if temp_audio:
        os.unlink(temp_audio.name)


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe with Whisper + anabolics vocabulary"
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Video/audio file to transcribe"
    )
    parser.add_argument(
        "--url",
        help="YouTube URL to download and transcribe"
    )
    parser.add_argument(
        "--out", "-o",
        help="Output directory or file path"
    )
    parser.add_argument(
        "--channel",
        help="Process all videos in a channel directory"
    )

    args = parser.parse_args()

    client = get_client()

    if args.url:
        output_dir = Path(args.out) if args.out else Path(".")
        output_dir.mkdir(exist_ok=True)

        print(f"📥 Downloading: {args.url}")
        audio_path = download_youtube(args.url, output_dir)
        if audio_path:
            process_file(client, audio_path)
            os.remove(audio_path)  # Remove audio after transcription

    elif args.channel:
        channel_dir = Path("channels") / args.channel
        if not channel_dir.exists():
            print(f"❌ Channel directory not found: {channel_dir}")
            sys.exit(1)

        # Find media files without transcripts
        for media in channel_dir.glob("*"):
            if media.suffix.lower() in ['.mp4', '.mkv', '.webm', '.mp3']:
                txt_path = media.with_suffix('.txt')
                if not txt_path.exists():
                    process_file(client, media)

    elif args.input:
        output = Path(args.out) if args.out else None
        process_file(client, args.input, output)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
