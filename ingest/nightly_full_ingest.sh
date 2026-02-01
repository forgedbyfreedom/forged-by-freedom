#!/bin/bash
#
# 🌙 Nightly Full Ingest Pipeline
# --------------------------------
# 1. Download new transcripts from YouTube (rate-limited)
# 2. Apply vocabulary corrections
# 3. Rebuild master transcripts
# 4. Ingest to Pinecone
#
# Run via cron: 0 1 * * * /path/to/nightly_full_ingest.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/nightly_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "🌙 NIGHTLY FULL INGEST STARTING"
log "=========================================="

# Load environment
if [ -f "$SCRIPT_DIR/../.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/../.env" | xargs)
    log "✅ Loaded .env"
fi

# Step 1: Download transcripts
log ""
log "📥 STEP 1: Downloading transcripts from YouTube..."
log "------------------------------------------"
cd "$SCRIPT_DIR"
if ./overnight_channel_download.sh >> "$LOG_FILE" 2>&1; then
    log "✅ Transcript download complete"
else
    log "⚠️  Some channels may have failed (continuing...)"
fi

# Step 2: Apply corrections
log ""
log "🔧 STEP 2: Applying vocabulary corrections..."
log "------------------------------------------"
cd "$SCRIPT_DIR"
python3 fix_transcripts.py >> "$LOG_FILE" 2>&1
log "✅ Vocabulary corrections applied"

# Step 3: Rebuild master transcripts
log ""
log "📚 STEP 3: Rebuilding master transcripts..."
log "------------------------------------------"
cd "$SCRIPT_DIR/channels"
python3 build_master_transcripts.py >> "$LOG_FILE" 2>&1
log "✅ Master transcripts rebuilt"

# Step 4: Ingest to Pinecone
log ""
log "🚀 STEP 4: Ingesting to Pinecone..."
log "------------------------------------------"
cd "$SCRIPT_DIR"
python3 ingest_to_pinecone.py >> "$LOG_FILE" 2>&1
log "✅ Pinecone ingest complete"

# Stats
log ""
log "📊 STEP 5: Post-ingest stats..."
log "------------------------------------------"
python3 pinecone_stats.py >> "$LOG_FILE" 2>&1

log ""
log "=========================================="
log "🎯 NIGHTLY INGEST COMPLETE"
log "=========================================="
log "Log saved to: $LOG_FILE"
