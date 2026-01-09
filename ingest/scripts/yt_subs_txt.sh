#!/usr/bin/env bash

CHANNEL_URL="$1"
OUT_DIR="$2"

if [ -z "$CHANNEL_URL" ] || [ -z "$OUT_DIR" ]; then
  echo "Usage: yt_subs_txt.sh <channel_url> <output_dir>"
  exit 1
fi

mkdir -p "$OUT_DIR"

yt-dlp \
  --skip-download \
  --write-auto-sub \
  --sub-lang en \
  --sub-format vtt \
  --convert-subs txt \
  --no-warnings \
  --progress \
  -o "$OUT_DIR/%(title)s [%(id)s].%(ext)s" \
  "$CHANNEL_URL"
