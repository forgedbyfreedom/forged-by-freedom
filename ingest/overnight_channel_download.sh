#!/usr/bin/env bash
set -e

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $(pwd)/channels"
echo "🎯 Pinecone target (later ingest): forged-freedom-ai"
echo "=============================================="
echo ""

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"

TOTAL_EPISODES=0
TOTAL_TXT=0

# Safety check
if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "❌ yt-dlp not found in PATH"
  exit 1
fi

# Find every channel.url file
find "$CHANNELS_DIR" -name "channel.url" | while read CHANNEL_FILE; do
  CHANNEL_URL="$(cat "$CHANNEL_FILE")"
  CHANNEL_DIR="$(dirname "$CHANNEL_FILE")"

  echo "▶ Channel: $CHANNEL_URL"
  echo "📁 Output: $CHANNEL_DIR"
  echo "----------------------------------------------"

  yt-dlp \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --ignore-errors \
    --no-warnings \
    --restrict-filenames \
    -o "$CHANNEL_DIR/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"

  # Convert VTT → TXT
  for vtt in "$CHANNEL_DIR"/*.vtt; do
    [ -e "$vtt" ] || continue
    txt="${vtt%.vtt}.txt"
    sed 's/<[^>]*>//g' "$vtt" > "$txt"
    rm "$vtt"
    TOTAL_TXT=$((TOTAL_TXT + 1))
  done

  # Count episodes
  EP_COUNT=$(ls "$CHANNEL_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')
  TOTAL_EPISODES=$((TOTAL_EPISODES + EP_COUNT))

  echo "✅ Episodes so far: $TOTAL_EPISODES"
  echo ""
done

# Cleanup any leftover subtitle formats
find "$CHANNELS_DIR" -name "*.srt" -delete
find "$CHANNELS_DIR" -name "*.ass" -delete

echo "=============================================="
echo "✅ Overnight run complete"
echo "📺 Episodes collected: $TOTAL_EPISODES"
echo "📄 TXT files created: $TOTAL_TXT"
echo "=============================================="
