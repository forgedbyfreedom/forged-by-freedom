#!/usr/bin/env python3
"""
Speaker Detection for Multi-Host Shows
---------------------------------------
Detects and tags speaker segments in transcripts for shows like:
- Blood Sweat and Gear (Scott McNally, Dave Crosland, Skipp Hill)
- RXMuscle episodes
- Interview-style content

Methods:
1. Pattern-based detection (name mentions, Q:/A: format)
2. Host voice signatures (common phrases per host)
3. Segment-based speaker assignment

Usage:
    python speaker_detection.py transcript.txt           # Single file
    python speaker_detection.py --channel @ThinkBIGBodybuilding  # All channel files
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

# ThinkBig hosts and their signature phrases
THINKBIG_HOSTS = {
    "Scott McNally": [
        "i'll tell you what", "here's the thing", "let me tell you",
        "in my experience", "when i was competing", "years ago",
        "real talk", "bottom line"
    ],
    "Dave Crosland": [
        "in the uk", "british", "england", "mate", "proper",
        "fundamentally", "the reality is", "scientifically speaking",
        "from a medical standpoint"
    ],
    "Skipp Hill": [
        "conditioning", "cardio", "prep", "getting stage ready",
        "when i work with clients", "from a coaching perspective",
        "in terms of", "bodybuilding wise"
    ]
}

# Common guest indicators
GUEST_PATTERNS = [
    r"our guest today",
    r"joining us is",
    r"we have .+ with us",
    r"welcome to the show",
    r"thanks for having me"
]

# Interview patterns (Q/A format)
INTERVIEW_PATTERNS = [
    (r"^\s*Q[:\.]", "Interviewer"),
    (r"^\s*A[:\.]", "Guest"),
    (r"^(Host|Interviewer):", "Host"),
    (r"^(Guest|Speaker):", "Guest"),
]


def detect_thinkbig_speakers(text: str) -> dict:
    """
    Analyze ThinkBig transcript to estimate speaker presence.
    Returns dict of {speaker: estimated_percentage}
    """
    text_lower = text.lower()
    scores = defaultdict(float)

    for host, phrases in THINKBIG_HOSTS.items():
        for phrase in phrases:
            count = text_lower.count(phrase)
            scores[host] += count * 2  # Weight phrase matches

    # Check for name mentions
    for host in THINKBIG_HOSTS.keys():
        first_name = host.split()[0].lower()
        scores[host] += text_lower.count(first_name) * 0.5

    # Normalize to percentages
    total = sum(scores.values()) or 1
    return {host: round(score / total * 100, 1)
            for host, score in scores.items() if score > 0}


def detect_guest_speaker(text: str):
    """Try to extract guest name from transcript."""
    for pattern in GUEST_PATTERNS:
        match = re.search(pattern + r'\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text)
        if match:
            return match.group(1)
    return None


def segment_by_topic(text: str, chunk_size: int = 500):
    """
    Split transcript into topic-based segments.
    Each segment gets speaker attribution based on context.
    """
    words = text.split()
    segments = []

    for i in range(0, len(words), chunk_size):
        segment_text = ' '.join(words[i:i + chunk_size])
        speakers = detect_thinkbig_speakers(segment_text)

        segments.append({
            'text': segment_text,
            'start_word': i,
            'end_word': min(i + chunk_size, len(words)),
            'speakers': speakers
        })

    return segments


def add_speaker_metadata(transcript_path: Path, channel: str = None) -> dict:
    """
    Analyze transcript and return speaker metadata.

    Returns:
        {
            'primary_speakers': ['Scott McNally', 'Dave Crosland'],
            'speaker_distribution': {'Scott McNally': 45.2, ...},
            'guest': 'Ron Partlow' or None,
            'format': 'multi-host' | 'interview' | 'solo'
        }
    """
    text = transcript_path.read_text(encoding='utf-8')

    # Detect ThinkBig speakers
    speaker_dist = detect_thinkbig_speakers(text)

    # Try to detect guest
    guest = detect_guest_speaker(text)

    # Determine format
    if len(speaker_dist) >= 2:
        format_type = 'multi-host'
    elif any(re.search(p[0], text, re.MULTILINE) for p in INTERVIEW_PATTERNS):
        format_type = 'interview'
    else:
        format_type = 'solo'

    # Primary speakers (above 15% presence)
    primary = [s for s, pct in speaker_dist.items() if pct >= 15]

    return {
        'primary_speakers': primary or ['Unknown'],
        'speaker_distribution': speaker_dist,
        'guest': guest,
        'format': format_type
    }


def enrich_transcript_for_ingest(transcript_path: Path, channel: str) -> dict:
    """
    Generate enriched metadata for Pinecone ingest.
    Called during ingestion to add speaker info.
    """
    metadata = add_speaker_metadata(transcript_path, channel)

    # Format speaker string for display
    if metadata['guest']:
        speakers = f"{', '.join(metadata['primary_speakers'])} with {metadata['guest']}"
    else:
        speakers = ', '.join(metadata['primary_speakers'])

    return {
        'speakers': speakers,
        'speaker_list': metadata['primary_speakers'],
        'guest': metadata['guest'],
        'format': metadata['format'],
        'speaker_distribution': metadata['speaker_distribution']
    }


def process_channel(channel_dir: Path):
    """Process all transcripts in a channel directory."""
    txt_files = list(channel_dir.glob("*.txt"))
    print(f"\n📂 Processing {len(txt_files)} transcripts in {channel_dir.name}")

    for txt_path in txt_files:
        if txt_path.name.startswith("master_"):
            continue

        try:
            metadata = add_speaker_metadata(txt_path, channel_dir.name)
            print(f"\n  📝 {txt_path.name[:50]}...")
            print(f"     Format: {metadata['format']}")
            print(f"     Speakers: {metadata['primary_speakers']}")
            if metadata['guest']:
                print(f"     Guest: {metadata['guest']}")
            if metadata['speaker_distribution']:
                dist = ', '.join(f"{k}: {v}%" for k, v in
                               sorted(metadata['speaker_distribution'].items(),
                                     key=lambda x: -x[1])[:3])
                print(f"     Distribution: {dist}")
        except Exception as e:
            print(f"  ❌ Error processing {txt_path.name}: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Speaker detection for transcripts")
    parser.add_argument("input", nargs="?", help="Transcript file to analyze")
    parser.add_argument("--channel", help="Process all files in channel directory")
    args = parser.parse_args()

    if args.channel:
        channel_dir = Path("channels") / args.channel
        if not channel_dir.exists():
            channel_dir = Path(args.channel)
        if channel_dir.exists():
            process_channel(channel_dir)
        else:
            print(f"❌ Channel not found: {args.channel}")
    elif args.input:
        path = Path(args.input)
        if path.exists():
            metadata = add_speaker_metadata(path)
            print(f"\n📝 {path.name}")
            print(f"Format: {metadata['format']}")
            print(f"Primary Speakers: {metadata['primary_speakers']}")
            if metadata['guest']:
                print(f"Guest: {metadata['guest']}")
            print(f"Distribution: {metadata['speaker_distribution']}")
        else:
            print(f"❌ File not found: {path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
