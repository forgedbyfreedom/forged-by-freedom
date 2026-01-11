#!/bin/bash

set -e

CHANNELS_DIR="$(pwd)/channels"
LOG_DIR="$(pwd)/logs"
LOG_FILE="$LOG_DIR/overnight_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

echo "==============================================" | tee -a "$LOG_FILE"
echo "🌙 Overnight Channel TXT Downloader (SAFE MODE)" | tee -a "$LOG_FILE"
echo "📂 Channels dir: $CHANNELS_DIR" | tee -a "$LOG_FILE"
echo "🕒 Sleep: 6–10s between videos (anti-rate-limit)" | tee -a "$LOG_FILE"
echo "==============================================" | tee -a "$LOG_FILE"

find "$CHANNELS_DIR" -name "channel.url" | while read -r CHANNEL_FILE; do
    CHANNEL_URL=$(head -n 1 "$CHANNEL_FILE")
    OUTPUT_DIR=$(dirname "$CHANNEL_FILE")

    echo "" | tee -a "$LOG_FILE"
    echo "▶ Channel: $CHANNEL_URL" | tee -a "$LOG_FILE"
    echo "📁 Output: $OUTPUT_DIR" | tee -a "$LOG_FILE"
    echo "----------------------------------------------" | tee -a "$LOG_FILE"

    yt-dlp \
        --skip-download \
        --write-subs \
        --write-auto-subs \
        --sub-lang en \
        --sub-format vtt \
        --output "$OUTPUT_DIR/%(title)s [%(id)s].%(ext)s" \
        --ignore-errors \
        --sleep-interval 6 \
        --max-sleep-interval 10 \
        "$CHANNEL_URL" >> "$LOG_FILE" 2>&1

done

echo "" | tee -a "$LOG_FILE"
echo "✅ Overnight ingest completed safely." | tee -a "$LOG_FILE"
