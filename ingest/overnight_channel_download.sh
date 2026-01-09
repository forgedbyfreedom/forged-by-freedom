#!/usr/bin/env bash
set -e

CHANNELS_DIR="$(cd "$(dirname "$0")/channels" && pwd)"

echo "🌙 Overnight TXT Transcript Download"
echo "📂 Channels dir: $CHANNELS_DIR"
echo "📄 Output: .txt subtitles"
echo "⏰ Started: $(date)"
echo "----------------------------------------"

# Process each folder under ingest/channels
for GROUP in "$CHANNELS_DIR"/*; do
  [ -d "$GROUP" ] || continue

  # If this is a "group folder" (e.g., thinkbig_tier0), process nested channel folders too
  # If it directly contains channel.url, treat it as a channel folder itself
  if [ -f "$GROUP/channel.url" ]; then
    CHANNEL_FOLDERS=("$GROUP")
  else
    CHANNEL_FOLDERS=("$GROUP"/*)
  fi

  for CH in "${CHANNEL_FOLDERS[@]}"; do
    [ -d "$CH" ] || continue
    [ -f "$CH/channel.url" ] || continue

    NAME="$(basename "$CH")"
    URL="$(cat "$CH/channel.url" | tr -d '\r' | head -n 1)"

    if [ -z "$URL" ]; then
      echo "⚠️  Skipping $NAME (empty channel.url)"
      continue
    fi

    echo ""
    echo "▶️  Channel: $NAME"
    echo "    URL: $URL"

    yt-dlp \
      --skip-download \
      --write-auto-sub \
      --sub-lang en \
      --sub-format vtt \
      --convert-subs txt \
      --no-overwrites \
      --continue \
      --ignore-errors \
      --sleep-interval 2 \
      --max-sleep-interval 6 \
      --retries 10 \
      --fragment-retries 10 \
      --socket-timeout 20 \
      --progress \
      --newline \
      --progress-template "download:%(progress.downloaded_entries)s/%(progress.total_entries)s episodes" \
      -o "$CH/%(title)s [%(id)s].%(ext)s" \
      "$URL"

  done
done

echo ""
echo "✅ Overnight TXT download complete"
echo "⏰ Finished: $(date)"
