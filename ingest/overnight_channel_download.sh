#!/usr/bin/env bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "🎯 Pinecone target (later ingest): forged-freedom-ai"
echo "=============================================="
echo ""

# Hard-path yt-dlp (venv-safe)
YTDLP="$(which yt-dlp)"

if [ ! -x "$YTDLP" ]; then
  echo "❌ yt-dlp not found"
  exit 1
fi

TOTAL_TXT=0

# Loop through every channel.url
find "$CHANNELS_DIR" -name "channel.url" | while read -r CHANNEL_FILE; do
  CHANNEL_URL=$(cat "$CHANNEL_FILE")
  OUT_DIR=$(dirname "$CHANNEL_FILE")

  echo "▶ Channel: $CHANNEL_URL"
  echo "📁 Output: $OUT_DIR"
  echo "----------------------------------------------"

  "$YTDLP" \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --no-playlist-reverse \
    --ignore-errors \
    -o "$OUT_DIR/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"

  # Convert VTT → TXT
  for vtt in "$OUT_DIR"/*.vtt; do
    [ -e "$vtt" ] || continue
    txt="${vtt%.vtt}.txt"
    sed 's/<[^>]*>//g' "$vtt" > "$txt"
    rm "$vtt"
    ((TOTAL_TXT++))
  done

  echo ""
done

# Cleanup
find "$CHANNELS_DIR" -name "*.srt" -delete

echo ""
echo "✅ Overnight run complete"
echo "📄 TXT files created: $TOTAL_TXT"
echo "=============================================="
