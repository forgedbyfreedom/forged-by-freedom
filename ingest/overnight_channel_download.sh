#!/usr/bin/env bash
set -euo pipefail

############################################
# 🌙 Overnight Channel TXT Downloader
# Forged by Freedom
############################################

# Resolve base directory
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"

# Virtualenv yt-dlp (explicit path)
VENV_YTDLP="$BASE_DIR/../venv/bin/yt-dlp"

# Safety checks
if [[ ! -x "$VENV_YTDLP" ]]; then
  echo "❌ yt-dlp not found at: $VENV_YTDLP"
  echo "👉 Activate venv and install yt-dlp:"
  echo "   source venv/bin/activate && pip install yt-dlp"
  exit 1
fi

if [[ ! -d "$CHANNELS_DIR" ]]; then
  echo "❌ Channels directory not found: $CHANNELS_DIR"
  exit 1
fi

echo "=============================================="
echo "🌙 Overnight Channel TXT Downloader"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "🎯 Pinecone target (later ingest): forged-freedom-ai"
echo "=============================================="
echo ""

TOTAL_TXT=0
TOTAL_EPISODES=0

############################################
# 📥 Download auto-subs per channel
############################################

find "$CHANNELS_DIR" -type f -name "channel.url" | while read -r URL_FILE; do
  CHANNEL_URL="$(cat "$URL_FILE")"
  CHANNEL_DIR="$(dirname "$URL_FILE")"

  echo "▶ Channel: $CHANNEL_URL"
  echo "📁 Output: $CHANNEL_DIR"
  echo "----------------------------------------------"

  "$VENV_YTDLP" \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --no-progress \
    --output "$CHANNEL_DIR/%(title)s [%(id)s].%(ext)s" \
    "$CHANNEL_URL"

done

############################################
# 🔄 Convert VTT → TXT
############################################

echo ""
echo "🔄 Converting subtitles to TXT..."

find "$CHANNELS_DIR" -name "*.vtt" | while read -r vtt; do
  txt="${vtt%.vtt}.txt"

  sed -E '
    /^[0-9]{2}:/d;
    /^[[:space:]]*$/d;
    s/<[^>]+>//g
  ' "$vtt" > "$txt"

  rm "$vtt"
  ((TOTAL_TXT+=1))
done

############################################
# 🧹 Cleanup
############################################

find "$CHANNELS_DIR" -name "*.srt" -delete
find "$CHANNELS_DIR" -name "*.ass" -delete

############################################
# ✅ Summary
############################################

TOTAL_EPISODES="$(find "$CHANNELS_DIR" -name "*.txt" | wc -l | tr -d ' ')"

echo ""
echo "=============================================="
echo "✅ Overnight run complete"
echo "📺 Total episodes (TXT): $TOTAL_EPISODES"
echo "📄 TXT files created this run: $TOTAL_TXT"
echo "=============================================="
