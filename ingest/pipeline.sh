#!/bin/bash
# ─────────────────────────────────────────────────────────────
# FORGED BY FREEDOM — UNIFIED INGEST PIPELINE
# ─────────────────────────────────────────────────────────────
# Nodes: cron → youtube → whisper → pinecone → search → answer
#
# Usage:
#   ./pipeline.sh              # Run full pipeline (download + fix + masters + ingest — NO Whisper)
#   ./pipeline.sh download     # YouTube download only (FREE — no Whisper)
#   ./pipeline.sh transcribe   # Whisper transcribe pending mp3s (FREE — local MLX Whisper)
#   ./pipeline.sh research     # PubMed + ClinicalTrials fetch
#   ./pipeline.sh fix          # Vocabulary corrections only
#   ./pipeline.sh ingest       # Pinecone ingest only
#   ./pipeline.sh stats        # Show stats only
# ─────────────────────────────────────────────────────────────

set +e  # Don't exit on errors — pipeline should always reach ingestion step

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Use venv Python (has dotenv, tiktoken, openai, pinecone installed)
# Allow PYTHON to be overridden from the environment (e.g. for mlx_whisper)
if [ -z "$PYTHON" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python3"
    [ -x "$PYTHON" ] || PYTHON="python3"
fi

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

# Add common paths for yt-dlp + deno
export PATH="$HOME/Library/Python/3.12/bin:$PATH:/opt/homebrew/bin:/usr/local/bin:$HOME/Library/Python/3.9/bin:$HOME/.local/bin"

# Use Python 3.12 yt-dlp (has latest YouTube extractors + EJS support)
YT_DLP="$HOME/Library/Python/3.12/bin/yt-dlp"
[ -x "$YT_DLP" ] || YT_DLP="yt-dlp"
command -v "$YT_DLP" >/dev/null 2>&1 || YT_DLP="python3 -m yt_dlp"

# ─── YouTube Cookie Setup ─────────────────────────────────────
# Refresh cookies from Chrome if it's running; fall back to saved cookies.txt
COOKIES_FILE="$SCRIPT_DIR/youtube_cookies.txt"
if pgrep -x "Google Chrome" > /dev/null 2>&1; then
    log "Chrome running — refreshing YouTube cookies..."
    $YT_DLP --cookies-from-browser chrome --cookies "$COOKIES_FILE" \
        --skip-download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" >> "$LOG_FILE" 2>&1 \
        && log "  ✓ Cookies refreshed" || log "  ⚠ Cookie refresh failed — using existing file"
else
    log "Chrome not running — using saved cookies file"
fi
YT_COOKIES="--cookies $COOKIES_FILE"

# ─── Channel Priority Tiers ──────────────────────────────────
# Tier 1: Primary sources — your core content (max 50 downloads)
TIER1="ThinkBIGBodybuilding|rxmuscle|anabolicbodybuilding|realtattered|TannerTatteredFAQ|johnjewett3"
# Tier 2: Key PED/fitness experts + female health + medical (max 30 downloads)
TIER2="AnabolicDoc|MorePlatesMoreDates|MPMD|vigoroussteve|LeoandLongevity|hubermanlab|AndrewHuberman|PeterAttiaMD|FoundMyFitness|GregDoucette|JohnMeadowsMountainDog|dorian_yates_official|FouadAbiad|RenaissancePeriodization|rpstrength|StanEfferding|JeffNippard|Biolayne|AthleanX|BarbellMedicine|GregNuckols|StrongerByScience|DrGabrielleLyon|DrStacySims|DrMindyPelz|HollyBaxter|SoheeFit|LaurinConlin|megsquats|StephanieButtermore|AshleyKaltwasser|ErinSternFitness|JulieLohre|KristyHawkins|Natacha_Oceane|StefiCohen|AbbeySharp|LoriHarder|MedCram|NinjaNerdOfficial|SquatUniversity|NorthwesternMed|TOTRevolution|gillettehealth|TaylorMadeCompounding|JayCampbell|DrCraigKoniver|TonyHuge|CoachTrevorBlack|TrevorBachmeyer|drtrevorbachmeyer|DrAndyGalpin|DrBradStanfield|Physionic|HighIntensityHealth|SethFeroce|MilosSarcev|HypertrophyCoach|MattJansen|BryanJohnson|DavidSinclair|MuscleIntelligence|3DMuscleJourney|EricHelms3DMJ|BradSchoenfeldPhD|BalanceMyHormones|DrAkshayJainMD|OmarIsuf"
# Skip: Not relevant to fitness/bodybuilding/PED coaching — already indexed content stays in Pinecone
SKIP_CHANNELS="3Blue1Brown|kurzgesagt|veritasium|Vsauce|numberphile|minutephysics|Vihart|StudyForce|AliAbdaal|melrobbins|MulliganBrothers|BroScienceLife|mitocw|Stanford|YaleCourses|ProfessorDaveExplains|TheRoyalInstitution|SciShow|TEDxTalks|TED|CarolineGirvan|HandwrittenTutorials|LecturioMedical|SketchyMedical|BoardsBeyond|USMLEFirstAid|NBMEmedical|Physeo|PathologyOutlines|ScienceNaturePage|NatureVideo|LancetTV|CellPress|PsychiatryOnline|Neurology|NeuroscientificallyC|CochraneCollaboration|BMJupdates|JAMANetwork|WHO|CDCgov|FDAChannel|NIH|ACPInternist"
# Low priority: Tangentially relevant (max 5 downloads per night)
LOW_PRIORITY="PickUpLimes|WhatIveLearned|ThomasDeLauer|VShred|WillTennyson|MattDoesFitness|BradleyMartyn|DavidGoggins|JockoPodcast|LondonReal"

# ─── Per-channel timeout (30 min max per channel) ───────────
CHANNEL_TIMEOUT=1800

get_max_downloads() {
    local channel="$1"
    echo "$channel" | grep -qE "$TIER1" && { echo 50; return; }
    echo "$channel" | grep -qE "$TIER2" && { echo 30; return; }
    echo "$channel" | grep -qE "$LOW_PRIORITY" && { echo 5; return; }
    echo 15  # Default for everything else
}

get_tier_label() {
    local channel="$1"
    echo "$channel" | grep -qE "$TIER1" && { echo "PRIORITY"; return; }
    echo "$channel" | grep -qE "$TIER2" && { echo "HIGH"; return; }
    echo "$channel" | grep -qE "$LOW_PRIORITY" && { echo "LOW"; return; }
    echo "MID"
}

# ─── Node 1: YouTube Download AUDIO + Whisper Transcribe ─────
download_and_transcribe() {
    header "NODE 1: YOUTUBE AUDIO DOWNLOAD + WHISPER TRANSCRIPTION"

    local SLEEP_MIN=3 SLEEP_MAX=8 SLEEP_BETWEEN=8 MAX_RETRIES=1
    local MAX_PARALLEL=4
    local count=0 success=0 failed=0 skipped=0

    log "Channels: $CHANNELS_DIR"
    log "Mode: Download audio → Whisper transcribe (${MAX_PARALLEL}x parallel) → Delete audio"
    log "Rate limit: ${SLEEP_MIN}-${SLEEP_MAX}s between videos"
    log "Tiers: PRIORITY(50) → HIGH(30) → MID(20) → LOW(10) | SKIP: irrelevant"

    # Build priority-sorted channel list into temp file
    local sorted_file=$(mktemp)
    find "$CHANNELS_DIR" -name "channel.url" | while IFS= read -r url_file; do
        local dir=$(dirname "$url_file")
        local name=$(basename "$dir")
        # Assign sort prefix by tier
        if echo "$name" | grep -qE "$SKIP_CHANNELS"; then
            echo "SKIP|$url_file"
        elif echo "$name" | grep -qE "$TIER1"; then
            echo "AAA|$url_file"
        elif echo "$name" | grep -qE "$TIER2"; then
            echo "BBB|$url_file"
        elif echo "$name" | grep -qE "$LOW_PRIORITY"; then
            echo "ZZZ|$url_file"
        else
            echo "CCC|$url_file"
        fi
    done | sort -t'|' -k1,1 | grep -v "^SKIP|" | cut -d'|' -f2 > "$sorted_file"

    local total_process=$(wc -l < "$sorted_file" | tr -d ' ')
    local total_all=$(find "$CHANNELS_DIR" -name "channel.url" | wc -l | tr -d ' ')
    skipped=$((total_all - total_process))

    log "Processing $total_process channels ($skipped skipped as irrelevant)"

    # Count transcripts before run
    local transcripts_before=$(find "$CHANNELS_DIR" -name "*.txt" ! -name "master_*" 2>/dev/null | wc -l | tr -d ' ')

    while IFS= read -r url_file; do
        local channel_url=$(head -n 1 "$url_file")
        local output_dir=$(dirname "$url_file")
        local channel_name=$(basename "$output_dir")
        local max_dl=$(get_max_downloads "$channel_name")
        local tier=$(get_tier_label "$channel_name")
        count=$((count + 1))

        log ""
        log "[$count/$total_process] $channel_name [$tier] (max $max_dl)"

        # Count channel transcripts before
        local ch_before=$(find "$output_dir" -name "*.txt" ! -name "master_*" 2>/dev/null | wc -l | tr -d ' ')

        # Download audio files (with per-channel timeout)
        local dl_done=false
        timeout $CHANNEL_TIMEOUT $YT_DLP \
            $YT_COOKIES \
            --extractor-args "youtubetab:skip=authcheck" \
            -x --audio-format mp3 --audio-quality 64K \
            --output "$output_dir/%(title)s [%(id)s].%(ext)s" \
            --ignore-errors --no-warnings \
            --sleep-interval $SLEEP_MIN --max-sleep-interval $SLEEP_MAX \
            --sleep-requests 1 \
            --extractor-retries 2 --fragment-retries 2 \
            --retry-sleep extractor:5 --retry-sleep http:3 \
            --download-archive "$output_dir/.downloaded" \
            --max-downloads $max_dl \
            "$channel_url" >> "$LOG_FILE" 2>&1
        local exit_code=$?
        if [ $exit_code -eq 0 ] || [ $exit_code -eq 101 ]; then
            # 0 = success, 101 = max-downloads reached (expected)
            dl_done=true
            success=$((success + 1))
            log "  ✓ Download complete"
        elif [ $exit_code -eq 124 ]; then
            # 124 = timeout hit
            failed=$((failed + 1))
            log "  ⏰ Timed out after ${CHANNEL_TIMEOUT}s — moving on"
        else
            failed=$((failed + 1))
            log "  ✗ Download failed (exit $exit_code)"
        fi

        # Count new mp3s (downloaded but not yet transcribed)
        local new_mp3s=$(find "$output_dir" -maxdepth 1 -name "*.mp3" 2>/dev/null | wc -l | tr -d ' ')
        [ "$new_mp3s" -gt 0 ] && log "  📥 $new_mp3s audio files downloaded (run './pipeline.sh transcribe' to transcribe — FREE local Whisper)"

        sleep $SLEEP_BETWEEN
    done < "$sorted_file"

    rm -f "$sorted_file"

    # Final stats
    local transcripts_after=$(find "$CHANNELS_DIR" -name "*.txt" ! -name "master_*" 2>/dev/null | wc -l | tr -d ' ')
    local total_new=$((transcripts_after - transcripts_before))

    log ""
    log "Complete: $success channels, $total_new new transcripts, $failed failures, $skipped skipped"
}

# Legacy function for subtitle-only mode (faster but less coverage)
download_subtitles_only() {
    header "NODE 1-ALT: SUBTITLE DOWNLOAD ONLY (Fast Mode)"

    local SLEEP_MIN=15 SLEEP_MAX=45 SLEEP_BETWEEN=120 MAX_RETRIES=3
    local count=0 success=0 failed=0

    for url_file in $(find "$CHANNELS_DIR" -name "channel.url" | awk 'BEGIN{srand()}{print rand()"\t"$0}' | sort -n | cut -f2-); do
        local channel_url=$(head -n 1 "$url_file")
        local output_dir=$(dirname "$url_file")
        local channel_name=$(basename "$output_dir")
        count=$((count + 1))

        log "[$count] $channel_name"

        if $YT_DLP \
            $YT_COOKIES \
            --skip-download \
            --write-subs --write-auto-subs \
            --sub-lang en \
            --sub-format "best" \
            --convert-subs srt \
            --output "$output_dir/%(title)s [%(id)s].%(ext)s" \
            --ignore-errors --no-warnings \
            --sleep-interval $SLEEP_MIN --max-sleep-interval $SLEEP_MAX \
            --download-archive "$output_dir/.downloaded" \
            "$channel_url" >> "$LOG_FILE" 2>&1; then
            success=$((success + 1))
        else
            failed=$((failed + 1))
        fi
        sleep $SLEEP_BETWEEN
    done

    log "Subtitle download: $success succeeded, $failed failed"
}

# ─── Node 1b: Fetch Research Data ────────────────────────────
fetch_research() {
    header "NODE 1b: RESEARCH DATA (PubMed + ClinicalTrials + Web Scrapers)"
    cd "$SCRIPT_DIR"

    log "Fetching PubMed abstracts..."
    $PYTHON -u fetch_pubmed.py --max 50 2>&1 | tee -a "$LOG_FILE" || log "  ⚠ PubMed fetch had errors"

    log ""
    log "Fetching ClinicalTrials.gov data..."
    $PYTHON -u fetch_clinicaltrials.py --max 50 2>&1 | tee -a "$LOG_FILE" || log "  ⚠ ClinicalTrials fetch had errors"

    log ""
    log "Scraping ThinkSteroids.com compound profiles..."
    python3 -u scrape_thinksteroids.py 2>&1 | tee -a "$LOG_FILE" || log "  ⚠ ThinkSteroids scraper had errors"

    log ""
    log "Scraping Ergo-Log.com research articles..."
    python3 -u scrape_ergolog.py 2>&1 | tee -a "$LOG_FILE" || log "  ⚠ Ergo-Log scraper had errors"
}

# ─── Node 1c: Whisper Transcription (FREE — local MLX Whisper on Apple Silicon) ────
transcribe_pending() {
    header "NODE 1c: LOCAL WHISPER TRANSCRIPTION (FREE — MLX/faster-whisper)"
    local MAX_PARALLEL=1  # GPU inference is serial — model handles batching internally
    local count=0 transcribed=0

    # Count pending mp3s
    local pending=$(find "$CHANNELS_DIR" -name "*.mp3" | wc -l | tr -d ' ')
    log "Pending mp3 files: $pending"

    if [ "$pending" -eq 0 ]; then
        log "No mp3 files to transcribe. Download first with './pipeline.sh download'"
        return
    fi

    # Estimate audio duration
    local total_mb=$(find "$CHANNELS_DIR" -name "*.mp3" -exec du -k {} + 2>/dev/null | awk '{sum+=$1} END {printf "%.0f", sum/1024}')
    local est_minutes=$((total_mb * 1024 / 8 / 60))  # 64kbps = 8KB/s
    log "Estimated: ~${est_minutes} minutes of audio"
    log "💰 Cost: FREE (running locally on Apple Silicon)"

    find "$CHANNELS_DIR" -name "*.mp3" -print0 | sort -z | while IFS= read -r -d '' mp3; do
        [ -f "$mp3" ] || continue
        local txt="${mp3%.mp3}.txt"
        if [ ! -f "$txt" ]; then
            count=$((count + 1))
            log "  [$count/$pending] 🎤 Transcribing: $(basename "$mp3")"
            if $PYTHON -u "$SCRIPT_DIR/whisper_transcribe.py" "$mp3" >> "$LOG_FILE" 2>&1; then
                rm -f "$mp3"
                transcribed=$((transcribed + 1))
                log "  ✅ Done: $(basename "$mp3")"
            else
                log "  ❌ Failed: $(basename "$mp3")"
            fi
        else
            rm -f "$mp3"  # Already have transcript
        fi
    done
    log "Transcribed $transcribed files"
}

# ─── Node 2: Vocabulary Corrections (Whisper post-process) ────
fix_transcripts() {
    header "NODE 2: VOCABULARY CORRECTIONS"
    cd "$SCRIPT_DIR"
    $PYTHON -u fix_transcripts.py 2>&1 | tee -a "$LOG_FILE"
}

# ─── Node 3: Build Master Transcripts ─────────────────────────
build_masters() {
    header "NODE 3: BUILD MASTER TRANSCRIPTS"
    cd "$SCRIPT_DIR"
    $PYTHON -u build_master_transcripts.py 2>&1 | tee -a "$LOG_FILE"
}

# ─── Node 4: Pinecone Ingest ──────────────────────────────────
ingest_pinecone() {
    header "NODE 4: PINECONE INGEST"
    cd "$SCRIPT_DIR"
    $PYTHON -u ingest_to_pinecone.py 2>&1 | tee -a "$LOG_FILE"
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
        $PYTHON -u pinecone_stats.py 2>&1 | tee -a "$LOG_FILE"
    fi

    # Generate and push live stats for AI coach display
    if [ -f "$SCRIPT_DIR/generate_stats.sh" ]; then
        bash "$SCRIPT_DIR/generate_stats.sh" 2>&1 | tee -a "$LOG_FILE"
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
        download)   download_and_transcribe ;;      # Download audio only (FREE)
        transcribe) transcribe_pending ;;            # Local Whisper transcribe (FREE)
        subs-only)  download_subtitles_only ;;      # Fast: subtitles only
        research)   fetch_research ;;
        fix)        fix_transcripts ;;
        masters)    build_masters ;;
        ingest)     ingest_pinecone ;;
        stats)      show_stats ;;
        full)
            # Downloads can fail — never block ingestion of existing content
            download_and_transcribe || log "⚠ Some downloads failed — continuing with ingestion"
            fetch_research || log "⚠ Research fetch had issues — continuing"
            fix_transcripts
            build_masters
            ingest_pinecone
            show_stats
            ;;
        fast)
            # Fast mode: subtitles only (for channels with good auto-captions)
            download_subtitles_only
            fetch_research
            fix_transcripts
            build_masters
            ingest_pinecone
            show_stats
            ;;
        auto)
            # Auto-loop: keeps running full pipeline until no new content found
            local run=1
            while true; do
                header "AUTO RUN #$run"
                local before=$(find "$CHANNELS_DIR" -name "*.txt" ! -name "master_*" 2>/dev/null | wc -l | tr -d ' ')

                download_and_transcribe
                fetch_research
                fix_transcripts
                build_masters
                ingest_pinecone
                show_stats

                local after=$(find "$CHANNELS_DIR" -name "*.txt" ! -name "master_*" 2>/dev/null | wc -l | tr -d ' ')
                local gained=$((after - before))

                log ""
                log "Run #$run complete: $gained new transcripts (total: $after)"

                if [ "$gained" -eq 0 ]; then
                    log "No new content found — backlog fully processed!"
                    break
                fi

                run=$((run + 1))
                log "New content found. Restarting in 60 seconds..."
                sleep 60

                # Refresh log file for new run
                TIMESTAMP=$(date +%Y%m%d_%H%M%S)
                LOG_FILE="$LOG_DIR/pipeline_$TIMESTAMP.log"
            done
            ;;
        *)
            echo "Usage: $0 {full|fast|download|subs-only|research|fix|masters|ingest|stats|auto}"
            echo ""
            echo "  full      - Download audio + local Whisper transcribe (thorough, FREE)"
            echo "  fast      - Download subtitles only (quick but limited)"
            echo "  auto      - Loop full pipeline until all channels fully processed"
            echo "  download  - Audio + Whisper only"
            echo "  subs-only - Subtitles only"
            echo "  research  - PubMed + ClinicalTrials"
            echo "  fix       - Vocabulary corrections"
            echo "  masters   - Build master transcripts"
            echo "  ingest    - Pinecone ingest"
            echo "  stats     - Show statistics"
            exit 1
            ;;
    esac

    header "PIPELINE COMPLETE"
    log "Finished: $(date)"
}

main "$@"
