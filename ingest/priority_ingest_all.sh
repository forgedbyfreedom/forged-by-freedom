#!/bin/bash
#
# 🔥 Priority Ingest Pipeline — Downloads, Transcribes, and Ingests
# Runs through ALL priority channels in order, then moves to the rest.
# Rate-limited to avoid YouTube bans.
#
# Usage: nohup bash priority_ingest_all.sh > logs/priority_run.log 2>&1 &
#

set -e
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$SCRIPT_DIR/channels"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/priority_$(date +%Y%m%d_%H%M%S).log"
PYTHON="$SCRIPT_DIR/.venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3"

mkdir -p "$LOG_DIR"

YT_DLP="yt-dlp"
command -v yt-dlp >/dev/null 2>&1 || YT_DLP="python3 -m yt_dlp"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# Rate limit settings
SLEEP_BETWEEN_VIDS=20
SLEEP_BETWEEN_CHANNELS=90

# ═══════════════════════════════════════════════════════════════
# PRIORITY TIERS — processed in order
# ═══════════════════════════════════════════════════════════════

TIER1_CORE=(
    "@J3University"
    "@hubermanlab"
    "@rxmuscle"
    "@HollyBaxter"
    "@MorePlatesMoreDates"
    "@ThinkBigBodybuilding"
    "@AnabolicBodybuilding"
)

TIER2_LEGENDS=(
    "@JayCutlerTV"
    "@PhilHeath"
    "@LeeHaney"
    "@KaiGreene"
)

TIER3_FEMALE=(
    "@LaurinConlin"
    "@StefiCohen"
    "@StephanieButtermore"
    "@megsquats"
    "@DrStacySims"
    "@drmaryclairehaver"
    "@DrMindyPelz"
    "@ErinSternFitness"
    "@SoheeFit"
    "@CarolineGirvan"
    "@coachmusclenugget"
    "@LoriHarder"
)

TIER4_SCIENCE=(
    "@GregDoucette"
    "@JeffNippard"
    "@RenaissancePeriodization"
    "@StrongerByScience"
    "@ReviveStronger"
    "@drandygalpin"
    "@BretContreras1"
    "@joeydsmith"
)

TIER6_NUTRITION=(
    "@nutritionfactsorg"
)

TIER5_MEDICAL=(
    "@MedCram"
    "@DrEricBerg"
    "@FoundMyFitness"
    "@PeterAttiaMD"
    "@DukeHealth"
    "@ClevelandClinic"
    "@MayoClinic"
)

# Combine all tiers
ALL_PRIORITY=("${TIER1_CORE[@]}" "${TIER2_LEGENDS[@]}" "${TIER3_FEMALE[@]}" "${TIER4_SCIENCE[@]}" "${TIER5_MEDICAL[@]}" "${TIER6_NUTRITION[@]}")

download_channel() {
    local CHANNEL="$1"
    local CHANNEL_DIR="$CHANNELS_DIR/$CHANNEL"
    mkdir -p "$CHANNEL_DIR"

    log "📥 Downloading: $CHANNEL"

    # Download subtitles/transcripts only (no video)
    $YT_DLP \
        --write-auto-sub \
        --sub-lang en \
        --skip-download \
        --write-subs \
        --convert-subs txt \
        --no-overwrites \
        --ignore-errors \
        --no-warnings \
        --sleep-interval $SLEEP_BETWEEN_VIDS \
        --max-sleep-interval $((SLEEP_BETWEEN_VIDS + 15)) \
        --sleep-requests 5 \
        --extractor-retries 3 \
        --output "$CHANNEL_DIR/%(title)s [%(id)s].%(ext)s" \
        "https://www.youtube.com/$CHANNEL/videos" \
        >> "$LOG_FILE" 2>&1 || {
            log "  ⚠️  $CHANNEL had errors (partial download OK)"
        }

    # Count what we got
    local COUNT=$(ls "$CHANNEL_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')
    log "  ✅ $CHANNEL: $COUNT transcripts on disk"
}

transcribe_and_ingest() {
    log ""
    log "═══════════════════════════════════════════"
    log "📝 TRANSCRIBING & INGESTING TO PINECONE"
    log "═══════════════════════════════════════════"

    # Convert any .srt files to .txt
    if [ -f "$SCRIPT_DIR/srt_to_txt.py" ]; then
        log "Converting SRT → TXT..."
        $PYTHON "$SCRIPT_DIR/srt_to_txt.py" 2>&1 | tee -a "$LOG_FILE" || true
    fi

    # Apply vocabulary corrections
    if [ -f "$SCRIPT_DIR/anabolics_vocabulary.py" ]; then
        log "Applying vocabulary corrections..."
        $PYTHON "$SCRIPT_DIR/anabolics_vocabulary.py" 2>&1 | tee -a "$LOG_FILE" || true
    fi

    # Build master transcripts
    if [ -f "$SCRIPT_DIR/build_master_transcripts.py" ]; then
        log "Building master transcripts..."
        $PYTHON "$SCRIPT_DIR/build_master_transcripts.py" 2>&1 | tee -a "$LOG_FILE" || true
    fi

    # Ingest to Pinecone
    if [ -f "$SCRIPT_DIR/ingest_to_pinecone.py" ]; then
        log "Ingesting to Pinecone..."
        $PYTHON "$SCRIPT_DIR/ingest_to_pinecone.py" 2>&1 | tee -a "$LOG_FILE" || true
    fi

    log "✅ Transcription & ingest complete"
}

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

log "═══════════════════════════════════════════"
log "🔥 FBF PRIORITY INGEST PIPELINE"
log "📊 ${#ALL_PRIORITY[@]} priority channels"
log "═══════════════════════════════════════════"

COMPLETED=0
TOTAL=${#ALL_PRIORITY[@]}

for CHANNEL in "${ALL_PRIORITY[@]}"; do
    COMPLETED=$((COMPLETED + 1))
    log ""
    log "[$COMPLETED/$TOTAL] Processing $CHANNEL"

    download_channel "$CHANNEL"

    # After each tier, run transcription + ingest
    # Tier 1 = first 9, Tier 2 = next 12, etc.
    if [ $COMPLETED -eq 7 ] || [ $COMPLETED -eq 11 ] || [ $COMPLETED -eq 23 ] || [ $COMPLETED -eq 28 ] || [ $COMPLETED -eq $TOTAL ]; then
        transcribe_and_ingest
    fi

    # Sleep between channels to avoid rate limits
    if [ $COMPLETED -lt $TOTAL ]; then
        log "  💤 Sleeping ${SLEEP_BETWEEN_CHANNELS}s before next channel..."
        sleep $SLEEP_BETWEEN_CHANNELS
    fi
done

# ═══════════════════════════════════════════════════════════════
# NOW PROCESS REMAINING NON-PRIORITY CHANNELS
# ═══════════════════════════════════════════════════════════════

log ""
log "═══════════════════════════════════════════"
log "📦 Processing remaining channels..."
log "═══════════════════════════════════════════"

PRIORITY_SET=$(printf '%s\n' "${ALL_PRIORITY[@]}")

for CHANNEL_DIR in "$CHANNELS_DIR"/*/; do
    CHANNEL_NAME=$(basename "$CHANNEL_DIR")
    # Skip if already processed as priority
    if echo "$PRIORITY_SET" | grep -q "$CHANNEL_NAME"; then
        continue
    fi

    COMPLETED=$((COMPLETED + 1))
    log "[$COMPLETED] $CHANNEL_NAME (non-priority)"
    download_channel "$CHANNEL_NAME"

    # Ingest every 20 channels
    if [ $((COMPLETED % 20)) -eq 0 ]; then
        transcribe_and_ingest
    fi

    sleep $SLEEP_BETWEEN_CHANNELS
done

# Final ingest
transcribe_and_ingest

# Send ntfy notification when done
NTFY_TOPIC="${NTFY_TOPIC:-fbf-leads-bryan}"
curl -s -d "Priority ingest complete. $COMPLETED channels processed. Check logs." \
    -H "Title: ✅ FBF Ingest Pipeline Complete" \
    -H "Priority: default" \
    -H "Tags: books,white_check_mark" \
    "https://ntfy.sh/$NTFY_TOPIC" || true

log ""
log "═══════════════════════════════════════════"
log "🏁 ALL DONE — $COMPLETED channels processed"
log "═══════════════════════════════════════════"
