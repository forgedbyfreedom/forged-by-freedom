cat > download_medical_sources.sh << 'EOF'
#!/usr/bin/env bash

SOURCE_FILE="sources_medical.txt"
LOG_FILE="downloads/logs/medical_$(date +%Y%m%d_%H%M).log"

# Hardening against YouTube rate limits
SLEEP_MIN=15
SLEEP_MAX=45

while IFS="|" read -r category name url; do
    [[ -z "$url" ]] && continue

    echo "=== Downloading: $name ===" | tee -a "$LOG_FILE"

    yt-dlp \
      --ignore-errors \
      --no-abort-on-error \
      --sleep-interval $SLEEP_MIN \
      --max-sleep-interval $SLEEP_MAX \
      --concurrent-fragments 1 \
      --limit-rate 2M \
      --write-auto-sub \
      --sub-lang en \
      --sub-format vtt \
      --extract-audio \
      --audio-format wav \
      --audio-quality 0 \
      -o "downloads/audio/${name}/%(upload_date)s_%(title)s.%(ext)s" \
      "$url" >> "$LOG_FILE" 2>&1

done < "$SOURCE_FILE"

echo "=== COMPLETE ===" | tee -a "$LOG_FILE"
EOF
