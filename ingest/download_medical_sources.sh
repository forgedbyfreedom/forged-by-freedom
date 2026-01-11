cat > download_medical_sources.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

SOURCE_FILE="sources_medical.txt"
LOG_FILE="downloads/logs/medical_$(date +%Y%m%d_%H%M).log"

SLEEP_MIN=15
SLEEP_MAX=45

echo "Starting medical downloads..." | tee -a "$LOG_FILE"

while IFS="|" read -r category name url; do
    [[ -z "${url:-}" ]] && continue

    echo "-----------------------------------" | tee -a "$LOG_FILE"
    echo "Downloading channel: $name" | tee -a "$LOG_FILE"
    echo "URL: $url" | tee -a "$LOG_FILE"

    mkdir -p "downloads/audio/$name"

    yt-dlp \
      --ignore-errors \
      --no-abort-on-error \
      --sleep-interval "$SLEEP_MIN" \
      --max-sleep-interval "$SLEEP_MAX" \
      --concurrent-fragments 1 \
      --limit-rate 2M \
      --write-auto-sub \
      --sub-lang en \
      --sub-format vtt \
      --extract-audio \
      --audio-format wav \
      -o "downloads/audio/$name/%(upload_date)s_%(title)s.%(ext)s" \
      "$url" >> "$LOG_FILE" 2>&1

done < "$SOURCE_FILE"

echo "All downloads completed." | tee -a "$LOG_FILE"
EOF
