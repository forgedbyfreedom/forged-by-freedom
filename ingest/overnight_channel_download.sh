#!/bin/bash

# Ensure Homebrew binaries (yt-dlp, python3, etc.) are in PATH
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

set -e

CHANNELS_DIR="$(pwd)/channels"
LOG_DIR="$(pwd)/logs"
LOG_FILE="$LOG_DIR/overnight_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

# Anti-rate-limit settings (aggressive to avoid bans)
SLEEP_MIN=15
SLEEP_MAX=45
SLEEP_BETWEEN_CHANNELS=120
MAX_RETRIES=3
RETRY_WAIT=300

echo "==============================================" | tee -a "$LOG_FILE"
echo "🌙 Nightly Channel Downloader (RATE-LIMIT SAFE)" | tee -a "$LOG_FILE"
echo "📂 Channels dir: $CHANNELS_DIR" | tee -a "$LOG_FILE"
echo "🕒 Sleep: ${SLEEP_MIN}–${SLEEP_MAX}s between videos" | tee -a "$LOG_FILE"
echo "⏸️  Channel pause: ${SLEEP_BETWEEN_CHANNELS}s" | tee -a "$LOG_FILE"
echo "🔄 Retries: $MAX_RETRIES (wait ${RETRY_WAIT}s)" | tee -a "$LOG_FILE"
echo "📅 Schedule: Nightly" | tee -a "$LOG_FILE"
echo "==============================================" | tee -a "$LOG_FILE"

CHANNEL_COUNT=0
find "$CHANNELS_DIR" -name "channel.url" | awk 'BEGIN{srand()}{print rand()"\t"$0}' | sort -n | cut -f2- | while read -r CHANNEL_FILE; do
    CHANNEL_URL=$(head -n 1 "$CHANNEL_FILE")
    OUTPUT_DIR=$(dirname "$CHANNEL_FILE")
    CHANNEL_NAME=$(basename "$OUTPUT_DIR")
    CHANNEL_COUNT=$((CHANNEL_COUNT + 1))

    echo "" | tee -a "$LOG_FILE"
    echo "▶ [$CHANNEL_COUNT] $CHANNEL_NAME" | tee -a "$LOG_FILE"
    echo "📁 Output: $OUTPUT_DIR" | tee -a "$LOG_FILE"
    echo "----------------------------------------------" | tee -a "$LOG_FILE"

    RETRY=0
    SUCCESS=false

    while [ $RETRY -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
        if yt-dlp \
            --skip-download \
            --write-subs \
            --write-auto-subs \
            --sub-lang en \
            --sub-format vtt \
            --convert-subs srt \
            --output "$OUTPUT_DIR/%(title)s [%(id)s].%(ext)s" \
            --ignore-errors \
            --no-warnings \
            --sleep-interval "$SLEEP_MIN" \
            --max-sleep-interval "$SLEEP_MAX" \
            --sleep-requests 2 \
            --extractor-retries 3 \
            --fragment-retries 3 \
            --retry-sleep extractor:30 \
            --retry-sleep http:10 \
            --retry-sleep fragment:10 \
            --download-archive "$OUTPUT_DIR/.downloaded" \
            "$CHANNEL_URL" >> "$LOG_FILE" 2>&1; then
            SUCCESS=true
            echo "✅ $CHANNEL_NAME complete" | tee -a "$LOG_FILE"
        else
            RETRY=$((RETRY + 1))
            if [ $RETRY -lt $MAX_RETRIES ]; then
                echo "⚠️  Retry $RETRY/$MAX_RETRIES for $CHANNEL_NAME (waiting ${RETRY_WAIT}s)" | tee -a "$LOG_FILE"
                sleep $RETRY_WAIT
            else
                echo "❌ $CHANNEL_NAME failed after $MAX_RETRIES retries" | tee -a "$LOG_FILE"
            fi
        fi
    done

    # Pause between channels to avoid detection
    echo "⏸️  Pausing ${SLEEP_BETWEEN_CHANNELS}s before next channel..." | tee -a "$LOG_FILE"
    sleep $SLEEP_BETWEEN_CHANNELS

done

echo "" | tee -a "$LOG_FILE"
echo "✅ Nightly ingest completed at $(date)" | tee -a "$LOG_FILE"
