#!/bin/bash
# Priority download for female-specific channels
# These are boosted in Coach Bryan responses for women's health questions

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$SCRIPT_DIR/channels"
LOG_FILE="$SCRIPT_DIR/logs/female_priority_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$SCRIPT_DIR/logs"

# Add common paths
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:$HOME/Library/Python/3.9/bin:$HOME/.local/bin"

YT_DLP="yt-dlp"
command -v yt-dlp >/dev/null 2>&1 || YT_DLP="python3 -m yt_dlp"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# Female priority channels (in order of importance for PED/fitness content)
FEMALE_CHANNELS=(
    "@johnjewett3"           # J3 - female bodybuilding expert
    "@J3University"          # John Jewett's education channel
    "@HollyBaxter"           # Female bodybuilding coach
    "@LaurinConlin"          # Team Atlas - female competitors
    "@StefiCohen"            # Powerlifter, fitness
    "@StephanieButtermore"   # Science-based fitness
    "@megsquats"             # Powerlifting for women
    "@DrStacySims"           # Female physiology expert
    "@drmaryclairehaver"     # Menopause/hormones
    "@DrMindyPelz"           # Fasting for women
    "@KristyHawkins"         # IFBB Pro
    "@AshleyKaltwasser"      # 3x Bikini Olympia
    "@ErinSternFitness"      # 2x Figure Olympia
    "@SoheeFit"              # Evidence-based fitness
    "@Natacha_Oceane"        # Science-based training
    "@CarolineGirvan"        # Home workouts
    "@KatieCrewe"            # Glute training
    "@JulieLohre"            # Female fitness
    "@AbbeySharp"            # Dietitian
    "@coachmusclenugget"     # Female bodybuilding
    "@LoriHarder"            # Fitness entrepreneur
)

log "═══════════════════════════════════════════"
log "  FEMALE PRIORITY CHANNEL DOWNLOAD"
log "═══════════════════════════════════════════"
log "Channels: ${#FEMALE_CHANNELS[@]}"

count=0
for channel in "${FEMALE_CHANNELS[@]}"; do
    channel_dir="$CHANNELS_DIR/$channel"
    url_file="$channel_dir/channel.url"

    count=$((count + 1))

    if [ ! -f "$url_file" ]; then
        log "[$count] $channel - No URL file, skipping"
        continue
    fi

    channel_url=$(head -n 1 "$url_file")
    existing=$(find "$channel_dir" -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')

    if [ "$existing" -gt 10 ]; then
        log "[$count] $channel - Already has $existing transcripts, skipping"
        continue
    fi

    log "[$count] $channel - Downloading (has $existing transcripts)"

    # Download audio + transcribe
    if $YT_DLP \
        -x --audio-format mp3 --audio-quality 64K \
        --output "$channel_dir/%(title)s [%(id)s].%(ext)s" \
        --ignore-errors --no-warnings \
        --sleep-interval 15 --max-sleep-interval 45 \
        --sleep-requests 3 \
        --download-archive "$channel_dir/.downloaded" \
        --max-downloads 15 \
        "$channel_url" >> "$LOG_FILE" 2>&1; then
        log "  ✓ Audio downloaded"
    else
        log "  ⚠ Download had errors (may be rate limited)"
    fi

    # Transcribe mp3 files
    for mp3 in "$channel_dir"/*.mp3; do
        [ -f "$mp3" ] || continue
        txt="${mp3%.mp3}.txt"
        if [ ! -f "$txt" ]; then
            log "  🎤 Transcribing: $(basename "$mp3")"
            if python3 -u "$SCRIPT_DIR/whisper_transcribe.py" "$mp3" >> "$LOG_FILE" 2>&1; then
                log "    ✓ Transcribed"
                rm -f "$mp3"
            else
                log "    ✗ Transcription failed"
            fi
        else
            rm -f "$mp3"
        fi
    done

    # Rate limit between channels
    sleep 90
done

log ""
log "═══════════════════════════════════════════"
log "  FEMALE PRIORITY DOWNLOAD COMPLETE"
log "═══════════════════════════════════════════"
