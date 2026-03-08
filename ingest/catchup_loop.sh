#!/bin/bash
#
# 🔄 CONTINUOUS CATCH-UP PIPELINE
# --------------------------------
# Runs in a tight loop until all channels are caught up:
#   1. Download subtitles from a batch of channels
#   2. Fix vocab → rebuild masters → ingest to Pinecone
#   3. Repeat
#
# Usage: nohup ./catchup_loop.sh > logs/catchup_stdout.log 2>&1 &
# Stop:  kill $(cat /tmp/fbf_catchup.pid) or: pkill -f catchup_loop
#

set -o pipefail

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Use venv Python (has dotenv, tiktoken, openai, pinecone installed)
PYTHON="$SCRIPT_DIR/.venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3"
CHANNELS_DIR="$SCRIPT_DIR/channels"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="/tmp/fbf_catchup.pid"

# Write PID for easy stop
echo $$ > "$PID_FILE"

# Settings — faster than nightly but still respectful
BATCH_SIZE=10                  # Channels per batch before processing
SLEEP_BETWEEN_VIDEOS=5         # Seconds between video downloads (within channel)
MAX_SLEEP_BETWEEN_VIDEOS=15    # Max random sleep
SLEEP_BETWEEN_CHANNELS=30      # Seconds between channels (reduced from 120)
MAX_RETRIES=1                  # Only 1 retry per channel (don't waste time on dead ones)
RETRY_WAIT=30                  # Shorter retry wait
LOOP_PAUSE=60                  # Seconds between full loops

mkdir -p "$LOG_DIR"

# Load environment
if [ -f "$SCRIPT_DIR/../.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/../.env" | xargs)
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

LOOP=0

while true; do
    LOOP=$((LOOP + 1))
    LOG_FILE="$LOG_DIR/catchup_loop${LOOP}_$(date +%Y%m%d_%H%M%S).log"

    log "============================================"
    log "🔄 CATCH-UP LOOP #$LOOP STARTING"
    log "============================================"

    # Priority channels first, then the rest shuffled
    PRIORITY="@ThinkBIGBodybuilding @RPStrength @VigorousSteve @TRTandHormoneOptimization @SamSulek @rxmuscle @PubMedCentral @TrevorBachmeyer"
    PRIORITY_CHANNELS=""
    REST_CHANNELS=""
    for f in $(find "$CHANNELS_DIR" -name "channel.url"); do
        IS_PRIORITY=false
        for p in $PRIORITY; do
            if echo "$f" | grep -q "/$p/"; then
                IS_PRIORITY=true
                break
            fi
        done
        if [ "$IS_PRIORITY" = true ]; then
            PRIORITY_CHANNELS="${PRIORITY_CHANNELS}${f}"$'\n'
        else
            REST_CHANNELS="${REST_CHANNELS}${f}"$'\n'
        fi
    done
    SHUFFLED_REST=$(echo "$REST_CHANNELS" | sed '/^$/d' | awk 'BEGIN{srand()}{print rand()"\t"$0}' | sort -n | cut -f2-)
    ALL_CHANNELS=$(printf '%s\n%s' "$(echo "$PRIORITY_CHANNELS" | sed '/^$/d')" "$SHUFFLED_REST" | sed '/^$/d')
    TOTAL=$(echo "$ALL_CHANNELS" | wc -l | tr -d ' ')
    log "📂 Found $TOTAL channels (${#PRIORITY} priority channels first)"

    BATCH_NUM=0
    CHANNEL_NUM=0
    DOWNLOADED_THIS_LOOP=0

    echo "$ALL_CHANNELS" | while read -r CHANNEL_FILE; do
        [ -z "$CHANNEL_FILE" ] && continue

        CHANNEL_URL=$(head -n 1 "$CHANNEL_FILE")
        OUTPUT_DIR=$(dirname "$CHANNEL_FILE")
        CHANNEL_NAME=$(basename "$OUTPUT_DIR")
        CHANNEL_NUM=$((CHANNEL_NUM + 1))

        log ""
        log "▶ [$CHANNEL_NUM/$TOTAL] $CHANNEL_NAME"

        # Skip channels with known dead URLs (1970 dates = placeholder)
        if [ -z "$CHANNEL_URL" ]; then
            log "⏭️  Skipping (empty URL)"
            continue
        fi

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
                --sleep-interval "$SLEEP_BETWEEN_VIDEOS" \
                --max-sleep-interval "$MAX_SLEEP_BETWEEN_VIDEOS" \
                --sleep-requests 1 \
                --extractor-retries 2 \
                --retry-sleep extractor:10 \
                --retry-sleep http:5 \
                --download-archive "$OUTPUT_DIR/.downloaded" \
                --extractor-args "youtubetab:skip=authcheck" \
                "$CHANNEL_URL" >> "$LOG_FILE" 2>&1; then
                SUCCESS=true
                log "✅ $CHANNEL_NAME done"
                DOWNLOADED_THIS_LOOP=$((DOWNLOADED_THIS_LOOP + 1))
            else
                RETRY=$((RETRY + 1))
                if [ $RETRY -lt $MAX_RETRIES ]; then
                    log "⚠️  Retry $RETRY for $CHANNEL_NAME (${RETRY_WAIT}s)"
                    sleep $RETRY_WAIT
                else
                    log "❌ $CHANNEL_NAME failed — skipping"
                fi
            fi
        done

        sleep $SLEEP_BETWEEN_CHANNELS

        # Process after every BATCH_SIZE channels
        if [ $((CHANNEL_NUM % BATCH_SIZE)) -eq 0 ]; then
            BATCH_NUM=$((BATCH_NUM + 1))
            log ""
            log "📦 BATCH $BATCH_NUM COMPLETE ($CHANNEL_NUM channels done)"
            log "🔧 Processing: fix vocab → build masters → ingest..."

            # Fix transcripts
            cd "$SCRIPT_DIR"
            if $PYTHON fix_transcripts.py >> "$LOG_FILE" 2>&1; then
                log "✅ Vocab corrections applied"
            else
                log "⚠️  Vocab fix had errors (continuing)"
            fi

            # Rebuild masters
            cd "$SCRIPT_DIR/channels"
            if $PYTHON build_master_transcripts.py >> "$LOG_FILE" 2>&1; then
                log "✅ Masters rebuilt"
            else
                log "⚠️  Master build had errors (continuing)"
            fi

            # Ingest to Pinecone
            cd "$SCRIPT_DIR"
            if $PYTHON ingest_to_pinecone.py >> "$LOG_FILE" 2>&1; then
                log "✅ Pinecone ingest complete"
            else
                log "⚠️  Pinecone ingest had errors (continuing)"
            fi

            log "📊 Batch $BATCH_NUM processed. Continuing downloads..."
        fi
    done

    # Final processing for remaining channels in last partial batch
    log ""
    log "🔧 Final processing for loop #$LOOP..."

    cd "$SCRIPT_DIR"
    $PYTHON fix_transcripts.py >> "$LOG_FILE" 2>&1 || true
    cd "$SCRIPT_DIR/channels"
    $PYTHON build_master_transcripts.py >> "$LOG_FILE" 2>&1 || true
    cd "$SCRIPT_DIR"
    $PYTHON ingest_to_pinecone.py >> "$LOG_FILE" 2>&1 || true

    # Stats
    $PYTHON pinecone_stats.py >> "$LOG_FILE" 2>&1 || true

    log ""
    log "============================================"
    log "🔄 LOOP #$LOOP COMPLETE"
    log "============================================"
    log "⏳ Pausing ${LOOP_PAUSE}s before next loop..."
    sleep $LOOP_PAUSE
done
