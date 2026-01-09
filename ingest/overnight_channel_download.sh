#!/usr/bin/env bash
set -euo pipefail

############################################
# 🌙 Overnight Channel TXT Downloader
############################################

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"
VENV_YTDLP="$BASE_DIR/../venv/bin/yt-dlp"

PINECONE_INDEX="forged-freedom-ai"

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "🎯 Pinecone target (later ingest): $PINECONE_INDEX"
echo "=============================================="
echo ""

# --- Hard check yt-dlp ---
if [[ ! -x "$VENV_YTDLP" ]]; then
  echo "❌ yt-dlp not found at:"
  echo "   $VENV_YTDLP"
  echo ""
  echo "Fix with:"
  echo "  source venv/bin/activate"
  echo "  pip install -U yt-dlp"
  exit 1
fi

TOTAL_TXT=0
TOTAL_EPISODES=0

# --- Find all channel.url files ---
find "$CHANNELS_DIR" -type f -name "channel.url" | while read -r URLFILE; do
  CHANNEL_URL=$(cat "$URLFILE")
  CHANNEL_DIR=$(dirname "$URLFILE")

  echo "▶ Channel: $CHANNEL_URL"
  echo "📁 Output: $CHANNEL_DIR"
  echo "----------------------------------------------"

  "$VENV_YTDLP" \
    --quiet \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --output "$CHANNEL_DIR/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"

done

echo ""
echo "🔄 Converting subtitles to TXT..."

# --- Convert .vtt → .txt ---
find "$CHANNELS_DIR" -name "*.vtt" | while read -r vtt; do
  txt="${vtt%.vtt}.txt"
  sed 's/<[^>]*>//g' "$vtt" > "$txt"
  rm "$vtt"
  ((TOTAL_TXT+=1))
done

# --- Cleanup ---
find "$CHANNELS_DIR" -name "*.srt" -delete

TOTAL_EPISODES=$(find "$CHANNELS_DIR" -name "*.txt" | wc -l | tr -d ' ')

echo ""
echo "✅ Overnight run complete"
echo "📺 Episodes collected: $TOTAL_EPISODES"
echo "📄 TXT files created this run: $TOTAL_TXT"
echo "=============================================="
