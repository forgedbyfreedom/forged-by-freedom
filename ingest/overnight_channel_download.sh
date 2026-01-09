#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "=============================================="
echo ""

TOTAL_TXT=0
TOTAL_VTT=0
TOTAL_CHANNELS=0

# ----------------------------
# DOWNLOAD SUBTITLES PER CHANNEL
# ----------------------------
echo "📥 Downloading subtitles..."
echo ""

find "$CHANNELS_DIR" -name "channel.url" | while read -r URL_FILE; do
  CHANNEL_DIR="$(dirname "$URL_FILE")"
  CHANNEL_URL="$(cat "$URL_FILE")"

  ((TOTAL_CHANNELS+=1))

  echo "▶ Channel: $CHANNEL_URL"
  echo "📁 Output: $CHANNEL_DIR"

  yt-dlp \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --no-overwrites \
    -o "$CHANNEL_DIR/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"

  echo ""
done

# ----------------------------
# CONVERT VTT → TXT
# ----------------------------
echo "🔄 Converting subtitles to TXT..."
echo ""

find "$CHANNELS_DIR" -name "*.vtt" | while read -r vtt; do
  txt="${vtt%.vtt}.txt"
  sed 's/<[^>]*>//g' "$vtt" > "$txt"
  rm "$vtt"
  ((TOTAL_TXT+=1))
done

# Cleanup stray formats
find "$CHANNELS_DIR" -name "*.srt" -delete

echo ""
echo "✅ Overnight run complete"
echo "📺 Channels processed: $TOTAL_CHANNELS"
echo "📄 TXT files created: $TOTAL_TXT"
echo "=============================================="
