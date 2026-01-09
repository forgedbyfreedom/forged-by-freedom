#!/usr/bin/env bash
set -euo pipefail

############################################
# 🌙 Overnight YouTube → TXT Downloader
# macOS Bash 3 compatible
# Pinecone target (later ingest): forged-freedom-ai
############################################

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "🎯 Pinecone target (later ingest): forged-freedom-ai"
echo "=============================================="
echo ""

TOTAL_TXT=0
TOTAL_CHANNELS=0

# Find channel.url files (Bash 3 safe)
CHANNEL_URL_FILES=$(find "$CHANNELS_DIR" -type f -name "channel.url")

if [[ -z "$CHANNEL_URL_FILES" ]]; then
  echo "❌ No channel.url files found"
  exit 1
fi

# Loop channels
echo "$CHANNEL_URL_FILES" | while read -r URL_FILE; do
  CHANNEL_DIR="$(dirname "$URL_FILE")"
  CHANNEL_URL="$(cat "$URL_FILE")"

  TOTAL_CHANNELS=$((TOTAL_CHANNELS + 1))

  echo ""
  echo "▶ Channel: $CHANNEL_URL"
  echo "📁 Output: $CHANNEL_DIR"
  echo "----------------------------------------------"

  python3 -m yt_dlp \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --no-warnings \
    --sleep-interval 1 \
    --max-sleep-interval 3 \
    -o "$CHANNEL_DIR/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"

done

echo ""
echo "🔄 Converting subtitles to TXT..."
echo ""

# Convert VTT → TXT
find "$CHANNELS_DIR" -name "*.vtt" | while read -r vtt; do
  txt="${vtt%.vtt}.txt"
  sed 's/<[^>]*>//g' "$vtt" > "$txt"
  rm "$vtt"
  TOTAL_TXT=$((TOTAL_TXT + 1))
done

# Cleanup
find "$CHANNELS_DIR" -name "*.srt" -delete

echo ""
echo "=============================================="
echo "✅ Overnight run complete"
echo "📺 Channels processed: $TOTAL_CHANNELS"
echo "📄 TXT files created: $TOTAL_TXT"
echo "=============================================="
