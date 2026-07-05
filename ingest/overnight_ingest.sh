#!/usr/bin/env bash
set -euo pipefail

SOURCE_FILE="ingest/sources_medical.txt"
LOG_DIR="downloads/logs"
AUDIO_DIR="downloads/audio"
SUB_DIR="downloads/subs"

mkdir -p "$LOG_DIR" "$AUDIO_DIR" "$SUB_DIR"

LOG_FILE="$LOG_DIR/overnight_$(date +%Y%m%d_%H%M).log"

echo "=== Overnight ingest started at $(date) ===" | tee -a "$LOG_FILE"

while IFS="|" read -r category name url; do
  if [[ -z "${url:-}" ]]; then
    continue
  fi

  echo "----------------------------------------" | tee -a "$LOG_FILE"
  echo "Channel: $name" | tee -a "$LOG_FILE"
  echo "URL: $url" | tee -a "$LOG_FILE"

  mkdir -p "$AUDIO_DIR/$name" "$SUB_DIR/$name"

  yt-dlp \
    --cookies-from-browser chrome \
    --extractor-args "youtubetab:skip=authcheck" \
    --ignore-errors \
    --no-abort-on-error \
    --sleep-interval 20 \
    --max-sleep-interval 60 \
    --concurrent-fragments 1 \
    --limit-rate 1.5M \
    --write-auto-sub \
    --sub-lang en \
    --sub-format vtt \
    --extract-audio \
    --audio-format wav \
    --audio-quality 0 \
    -o "$AUDIO_DIR/$name/%(upload_date)s_%(id)s_%(title)s.%(ext)s" \
    "$url" >> "$LOG_FILE" 2>&1

  echo "Finished $name at $(date)" | tee -a "$LOG_FILE"

done < "$SOURCE_FILE"

echo "=== Overnight ingest completed at $(date) ===" | tee -a "$LOG_FILE"
