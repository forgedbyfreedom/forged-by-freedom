#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "=============================================="

if [ ! -d "$CHANNELS_DIR" ]; then
  echo "❌ channels directory not found"
  exit 1
fi

TOTAL_TXT=0

for CHANNEL_PATH in "$CHANNELS_DIR"/*; do
  [ -d "$CHANNEL_PATH" ] || continue

  URL_FILE="$CHANNEL_PATH/channel.url"
  [ -f "$URL_FILE" ] || continue

  CHANNEL_NAME="$(basename "$CHANNEL_PATH")"
  CHANNEL_URL="$(cat "$URL_FILE")"

  echo ""
  echo "▶️  $CHANNEL_NAME"

  yt-dlp \
    --write-auto-sub \
    --write-sub \
    --sub-lang en \
    --sub-format vtt \
    --skip-download \
    --sleep-interval 3 \
    --max-sleep-interval 10 \
    -o "$CHANNEL_PATH/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"
done

echo ""
echo "🔄 Converting subtitles to TXT..."

find "$CHANNELS_DIR" -name "*.vtt" -type f | while read -r vtt; do
  txt="${vtt%.vtt}.txt"
  sed 's/<[^>]*>//g' "$vtt" > "$txt"
  rm "$vtt"
  ((TOTAL_TXT+=1))
done

find "$CHANNELS_DIR" -name "*.srt" -delete

echo ""
echo "✅ Overnight run complete"
echo "📄 TXT files created: $TOTAL_TXT"
echo "=============================================="
