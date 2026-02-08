#!/bin/bash
# ─────────────────────────────────────────────────────────────
# SLOW DOWNLOAD - Rate-limit friendly YouTube downloader
# ─────────────────────────────────────────────────────────────
# Downloads 1-2 videos per channel with VERY long delays
# to avoid YouTube's rate limiting. Run via cron daily.
#
# Usage:
#   ./slow_download.sh                  # Download from priority channels
#   ./slow_download.sh @ChannelName     # Download from specific channel
#   ./slow_download.sh --all            # Download from all channels
# ─────────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$SCRIPT_DIR/channels"
LOG_FILE="$SCRIPT_DIR/logs/slow_download_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$SCRIPT_DIR/logs"
source "$SCRIPT_DIR/../.env" 2>/dev/null || true

export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:$HOME/Library/Python/3.9/bin"

YT_DLP="yt-dlp"
command -v yt-dlp >/dev/null 2>&1 || YT_DLP="python3 -m yt_dlp"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# VERY conservative rate limiting
SLEEP_MIN=60        # 1 minute minimum between requests
SLEEP_MAX=180       # 3 minutes maximum
SLEEP_CHANNEL=600   # 10 minutes between channels
MAX_PER_CHANNEL=2   # Only 2 videos per channel per run

# Priority channels (ThinkBig first, then female, then others)
PRIORITY_CHANNELS=(
    "@ThinkBIGBodybuilding"
    "@rxmuscle"
    "@anabolicbodybuilding"
    "@johnjewett3"
    "@DrGabrielleLyon"
    "@MorePlatesMoreDates"
    "@vigoroussteve"
    "@hubermanlab"
    "@PeterAttiaMD"
)

download_channel() {
    local channel="$1"
    local channel_dir="$CHANNELS_DIR/$channel"
    local url_file="$channel_dir/channel.url"

    if [ ! -f "$url_file" ]; then
        log "  ⚠ No URL file for $channel"
        return 1
    fi

    local channel_url=$(head -n 1 "$url_file")
    log "  📥 Downloading from $channel (max $MAX_PER_CHANNEL videos)"

    if $YT_DLP \
        --cookies-from-browser chrome \
        -x --audio-format mp3 --audio-quality 64K \
        --output "$channel_dir/%(title)s [%(id)s].%(ext)s" \
        --ignore-errors --no-warnings \
        --sleep-interval $SLEEP_MIN --max-sleep-interval $SLEEP_MAX \
        --sleep-requests 5 \
        --extractor-retries 5 --fragment-retries 5 \
        --retry-sleep extractor:120 --retry-sleep http:60 \
        --download-archive "$channel_dir/.downloaded" \
        --max-downloads $MAX_PER_CHANNEL \
        "$channel_url" >> "$LOG_FILE" 2>&1; then
        log "  ✓ Download complete"
        return 0
    else
        log "  ⚠ Download had errors"
        return 1
    fi
}

transcribe_channel() {
    local channel_dir="$1"
    local count=0

    for mp3 in "$channel_dir"/*.mp3; do
        [ -f "$mp3" ] || continue
        local txt="${mp3%.mp3}.txt"

        if [ ! -f "$txt" ]; then
            log "  🎤 Transcribing: $(basename "$mp3")"
            if python3 -u "$SCRIPT_DIR/whisper_transcribe.py" "$mp3" >> "$LOG_FILE" 2>&1; then
                log "    ✓ Transcribed"
                rm -f "$mp3"
                count=$((count + 1))
            else
                log "    ✗ Transcription failed"
            fi
        else
            rm -f "$mp3"
        fi
    done

    return $count
}

ingest_new() {
    log "📊 Running Pinecone ingest for new content..."
    cd "$SCRIPT_DIR"
    python3 -u ingest_to_pinecone.py >> "$LOG_FILE" 2>&1 &
    log "  ✓ Ingest started in background"
}

# ─── Main ─────────────────────────────────────────────────────
log "═══════════════════════════════════════════"
log "  SLOW DOWNLOAD - Rate Limit Friendly"
log "═══════════════════════════════════════════"
log "Sleep between videos: ${SLEEP_MIN}-${SLEEP_MAX}s"
log "Sleep between channels: ${SLEEP_CHANNEL}s"
log "Max videos per channel: $MAX_PER_CHANNEL"

if [ "$1" = "--all" ]; then
    # All channels
    channels=($(find "$CHANNELS_DIR" -name "channel.url" -exec dirname {} \; | xargs -n1 basename))
elif [ -n "$1" ]; then
    # Specific channel
    channels=("$1")
else
    # Priority channels only
    channels=("${PRIORITY_CHANNELS[@]}")
fi

log "Channels to process: ${#channels[@]}"
log ""

total_new=0
for channel in "${channels[@]}"; do
    log "[$channel]"
    channel_dir="$CHANNELS_DIR/$channel"

    if download_channel "$channel"; then
        transcribe_channel "$channel_dir"
        total_new=$((total_new + $?))
    fi

    log "  💤 Sleeping ${SLEEP_CHANNEL}s before next channel..."
    sleep $SLEEP_CHANNEL
done

log ""
log "═══════════════════════════════════════════"
log "  COMPLETE: $total_new new transcripts"
log "═══════════════════════════════════════════"

# If we got new content, run ingest
if [ $total_new -gt 0 ]; then
    ingest_new
fi
