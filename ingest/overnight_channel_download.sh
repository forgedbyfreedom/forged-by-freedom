#!/usr/bin/env bash
set -euo pipefail

############################################
# 🌙 Overnight YouTube → TXT Downloader
# Produces ingest-ready .txt transcripts
# Pinecone target: forged-freedom-ai (downstream)
############################################

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "🎯 Pinecone target (later ingest): forged-freedom-ai"
echo "=============================================="
echo ""

TOTAL_TXT=0
TOTAL_CHANNELS=0

# Find all channel.url files
mapfile -t CHANNEL_URLS < <(find "$CHANNELS_DIR" -type f -name "channel.url")

if [[ ${#CHANNEL_URLS[@]} -eq 0 ]]; then
  echo "❌ No channel.url files found"
  exit 1
fi

for URL_FILE in "${CHANNEL_URLS[@]}"; do
  CHANNEL_DIR="$(dirname "$URL_FILE")"
  CHANNEL_URL="$(cat "$URL_FILE")"

  ((TOTAL_CHANNELS+=1))

  echo ""
  echo "▶ Channel: $CHANNEL_URL"
  echo "📁 Output: $CHANNEL_DIR"
  echo "----------------------------------------------"

  # Download auto-subs only (no video)
  python3 -m yt_dlp \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --no-warnings \
    --no-playlist-reverse \
    --sleep-interval 1 \
    --max-sleep-interval 3 \
    -o "$CHANNEL_DIR/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"

done

echo ""
echo "🔄 Converting subtitles to TXT..."
echo ""

# Convert VTT → TXT and clean markup
while IFS= read -r vtt; do
  txt="${vtt%.vtt}.txt"
  sed 's/<[^>]*>//g' "$vtt" > "$txt"
  rm "$vtt"
  ((TOTAL_TXT+=1))
done < <(find "$CHANNELS_DIR" -name "*.vtt")

# Cleanup any stray SRTs
find "$CHANNELS_DIR" -name "*.srt" -delete

echo ""
echo "=============================================="
echo "✅ Overnight run complete"
echo "📺 Channels processed: $TOTAL_CHANNELS"
echo "📄 TXT files created: $TOTAL_TXT"
echo "=============================================="
