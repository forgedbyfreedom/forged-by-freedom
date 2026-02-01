#!/bin/bash
# ─────────────────────────────────────────────────────────────
# FORGED BY FREEDOM — UNIFIED INGEST PIPELINE
# ─────────────────────────────────────────────────────────────
# Nodes: cron → youtube → whisper → pinecone → search → answer
#
# Usage:
#   ./pipeline.sh              # Run full pipeline
#   ./pipeline.sh download     # YouTube download only
#   ./pipeline.sh fix          # Vocabulary corrections only
#   ./pipeline.sh ingest       # Pinecone ingest only
#   ./pipeline.sh stats        # Show stats only
# ─────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$SCRIPT_DIR/channels"
LOG_DIR="$SCRIPT_DIR/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/pipeline_$TIMESTAMP.log"

mkdir -p "$LOG_DIR"

# ─── Logging ──────────────────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }
header() { log ""; log "═══════════════════════════════════════════"; log "  $1"; log "═══════════════════════════════════════════"; }

# ─── Load Environment ─────────────────────────────────────────
if [ -f "$SCRIPT_DIR/../.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/../.env" | xargs)
fi

# ─── Node 1: YouTube Download ─────────────────────────────────
download_transcripts() {
    header "NODE 1: YOUTUBE TRANSCRIPT DOWNLOAD"

    local SLEEP_MIN=15 SLEEP_MAX=45 SLEEP_BETWEEN=120 MAX_RETRIES=3
    local count=0 success=0 failed=0

    log "Channels: $CHANNELS_DIR"
    log "Rate limit: ${SLEEP_MIN}-${SLEEP_MAX}s between videos, ${SLEEP_BETWEEN}s between channels"

    for url_file in $(find "$CHANNELS_DIR" -name "channel.url" | shuf); do
        local channel_url=$(head -n 1 "$url_file")
        local output_dir=$(dirname "$url_file")
        local channel_name=$(basename "$output_dir")
        count=$((count + 1))

        log ""
        log "[$count] $channel_name"

        local retry=0 done=false
        while [ $retry -lt $MAX_RETRIES ] && [ "$done" = false ]; do
            if yt-dlp \
                --skip-download \
                --write-subs --write-auto-subs \
                --sub-lang en --sub-format vtt --convert-subs txt \
                --output "$output_dir/%(title)s [%(id)s].%(ext)s" \
                --ignore-errors --no-warnings \
                --sleep-interval $SLEEP_MIN --max-sleep-interval $SLEEP_MAX \
                --sleep-requests 2 \
                --extractor-retries 3 --fragment-retries 3 \
                --retry-sleep extractor:30 --retry-sleep http:10 \
                --download-archive "$output_dir/.downloaded" \
                "$channel_url" >> "$LOG_FILE" 2>&1; then
                done=true
                success=$((success + 1))
                log "  ✓ Complete"
            else
                retry=$((retry + 1))
                [ $retry -lt $MAX_RETRIES ] && { log "  ⚠ Retry $retry/$MAX_RETRIES"; sleep 300; }
            fi
        done

        [ "$done" = false ] && { failed=$((failed + 1)); log "  ✗ Failed"; }
        sleep $SLEEP_BETWEEN
    done

    log ""
    log "Download complete: $success succeeded, $failed failed"
}

# ─── Node 2: Vocabulary Corrections (Whisper post-process) ────
fix_transcripts() {
    header "NODE 2: VOCABULARY CORRECTIONS"
    cd "$SCRIPT_DIR"
    python3 -u fix_transcripts.py 2>&1 | tee -a "$LOG_FILE"
}

# ─── Node 3: Build Master Transcripts ─────────────────────────
build_masters() {
    header "NODE 3: BUILD MASTER TRANSCRIPTS"
    cd "$SCRIPT_DIR"
    python3 -u build_master_transcripts.py 2>&1 | tee -a "$LOG_FILE"
}

# ─── Node 4: Pinecone Ingest ──────────────────────────────────
ingest_pinecone() {
    header "NODE 4: PINECONE INGEST"
    cd "$SCRIPT_DIR"
    python3 -u ingest_to_pinecone.py 2>&1 | tee -a "$LOG_FILE"
}

# ─── Node 5: Stats & Cleanup ──────────────────────────────────
show_stats() {
    header "NODE 5: STATS & CLEANUP"
    cd "$SCRIPT_DIR"

    # Channel count
    local channels=$(find "$CHANNELS_DIR" -maxdepth 1 -type d -name "@*" | wc -l | tr -d ' ')
    local transcripts=$(find "$CHANNELS_DIR" -name "*.txt" ! -name "master_*" | wc -l | tr -d ' ')

    log "Channels: $channels"
    log "Transcripts: $transcripts"

    # Pinecone stats
    if [ -f pinecone_stats.py ]; then
        python3 -u pinecone_stats.py 2>&1 | tee -a "$LOG_FILE"
    fi

    # Cleanup old logs (keep 7 days)
    find "$LOG_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null || true
    log "Cleaned logs older than 7 days"
}

# ─── Main ─────────────────────────────────────────────────────
main() {
    header "FORGED BY FREEDOM PIPELINE"
    log "Started: $(date)"
    log "Log: $LOG_FILE"

    case "${1:-full}" in
        download) download_transcripts ;;
        fix)      fix_transcripts ;;
        masters)  build_masters ;;
        ingest)   ingest_pinecone ;;
        stats)    show_stats ;;
        full)
            download_transcripts
            fix_transcripts
            build_masters
            ingest_pinecone
            show_stats
            ;;
        *)
            echo "Usage: $0 {full|download|fix|masters|ingest|stats}"
            exit 1
            ;;
    esac

    header "PIPELINE COMPLETE"
    log "Finished: $(date)"
}

main "$@"
