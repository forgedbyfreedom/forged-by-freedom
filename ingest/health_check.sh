#!/bin/bash
# ─────────────────────────────────────────────────────────────
# FORGED BY FREEDOM — PIPELINE HEALTH CHECK
# ─────────────────────────────────────────────────────────────
# Checks status of every pipeline node without running anything.
# Usage: ./health_check.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$SCRIPT_DIR/channels"
LOG_DIR="$SCRIPT_DIR/logs"

# Load env
[ -f "$SCRIPT_DIR/../.env" ] && export $(grep -v '^#' "$SCRIPT_DIR/../.env" | xargs)

export PATH="$HOME/Library/Python/3.12/bin:$PATH:/opt/homebrew/bin:/usr/local/bin:$HOME/Library/Python/3.9/bin:$HOME/.local/bin"

PYTHON="$SCRIPT_DIR/.venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3"

API_URL="${FBF_API_URL:-https://forged-by-freedom-api-nm4f.onrender.com}"

ok()   { echo "  ✅ $1"; }
warn() { echo "  ⚠️  $1"; }
fail() { echo "  ❌ $1"; }
hdr()  { echo ""; echo "── $1 ──────────────────────────────────────"; }

echo ""
echo "════════════════════════════════════════════"
echo "  FBF PIPELINE HEALTH CHECK  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════"

# ─── Tools ───────────────────────────────────────────────────
hdr "TOOLS"

YT_DLP="$HOME/Library/Python/3.12/bin/yt-dlp"
[ -x "$YT_DLP" ] || YT_DLP=$(command -v yt-dlp 2>/dev/null)
if [ -n "$YT_DLP" ] && [ -x "$YT_DLP" ]; then
    VER=$("$YT_DLP" --version 2>/dev/null)
    ok "yt-dlp $VER"
else
    fail "yt-dlp not found"
fi

if [ -x "$PYTHON" ]; then
    VER=$("$PYTHON" --version 2>/dev/null)
    ok "$PYTHON ($VER)"
else
    fail "Python venv not found at $PYTHON"
fi

if command -v deno >/dev/null 2>&1; then
    ok "deno $(deno --version 2>/dev/null | head -1)"
else
    warn "deno not found (needed for YouTube EJS challenges)"
fi

# ─── NODE 1: Downloads ────────────────────────────────────────
hdr "NODE 1 — DOWNLOADS"

TOTAL_CHANNELS=$(find "$CHANNELS_DIR" -name "channel.url" 2>/dev/null | wc -l | tr -d ' ')
CHANNELS_WITH_CONTENT=$(find "$CHANNELS_DIR" -mindepth 1 -maxdepth 1 -type d | while read -r d; do
    [ "$(find "$d" -name "*.txt" ! -name "channel.url" 2>/dev/null | wc -l)" -gt 0 ] && echo "1"
done | wc -l | tr -d ' ')
TOTAL_MP3S=$(find "$CHANNELS_DIR" -name "*.mp3" 2>/dev/null | wc -l | tr -d ' ')

ok "Channels registered: $TOTAL_CHANNELS"
ok "Channels with content: $CHANNELS_WITH_CONTENT"

if [ "$TOTAL_MP3S" -gt 0 ]; then
    warn "$TOTAL_MP3S mp3(s) pending transcription (run: ./pipeline.sh transcribe)"
else
    ok "No pending mp3s"
fi

COOKIES_FILE="$SCRIPT_DIR/youtube_cookies.txt"
if [ -f "$COOKIES_FILE" ]; then
    AGE_HOURS=$(( ( $(date +%s) - $(stat -f %m "$COOKIES_FILE") ) / 3600 ))
    if [ "$AGE_HOURS" -gt 48 ]; then
        warn "YouTube cookies are ${AGE_HOURS}h old (may be stale)"
    else
        ok "YouTube cookies fresh (${AGE_HOURS}h old)"
    fi
else
    warn "youtube_cookies.txt not found"
fi

# ─── NODE 1c: Whisper ─────────────────────────────────────────
hdr "NODE 1c — WHISPER TRANSCRIPTION"

WHISPER_SCRIPT="$SCRIPT_DIR/whisper_transcribe.py"
if [ -f "$WHISPER_SCRIPT" ]; then
    ok "whisper_transcribe.py present"
else
    fail "whisper_transcribe.py missing"
fi

if "$PYTHON" -c "import mlx_whisper" 2>/dev/null; then
    ok "mlx_whisper installed"
elif "$PYTHON" -c "import whisper" 2>/dev/null; then
    ok "openai-whisper installed (non-MLX)"
else
    warn "No Whisper module found (transcription unavailable)"
fi

# ─── NODE 2: Fix Transcripts ──────────────────────────────────
hdr "NODE 2 — VOCABULARY CORRECTIONS"

TOTAL_TXTS=$(find "$CHANNELS_DIR" -name "*.txt" ! -name "master_*" ! -name "channel.url" 2>/dev/null | wc -l | tr -d ' ')
ok "Individual transcripts: $TOTAL_TXTS"

FIX_SCRIPT="$SCRIPT_DIR/fix_transcripts.py"
if [ -f "$FIX_SCRIPT" ]; then
    ok "fix_transcripts.py present"
else
    fail "fix_transcripts.py missing"
fi

# ─── NODE 3: Master Transcripts ───────────────────────────────
hdr "NODE 3 — MASTER TRANSCRIPTS"

MASTER_COUNT=$(find "$CHANNELS_DIR" -name "master_*.txt" 2>/dev/null | wc -l | tr -d ' ')
ok "Master transcripts built: $MASTER_COUNT"

if [ "$MASTER_COUNT" -lt "$CHANNELS_WITH_CONTENT" ]; then
    MISSING=$((CHANNELS_WITH_CONTENT - MASTER_COUNT))
    warn "$MISSING channel(s) have content but no master (run: ./pipeline.sh masters)"
fi

# ─── NODE 4: Pinecone ─────────────────────────────────────────
hdr "NODE 4 — PINECONE"

if [ -n "$PINECONE_API_KEY" ]; then
    ok "PINECONE_API_KEY set"
else
    fail "PINECONE_API_KEY missing from .env"
fi

PINECONE_STATS="$SCRIPT_DIR/pinecone_stats.py"
if [ -f "$PINECONE_STATS" ]; then
    echo "  Running Pinecone stats..."
    PSTATS=$("$PYTHON" "$PINECONE_STATS" 2>&1)
    if echo "$PSTATS" | grep -qi "error\|exception\|failed"; then
        fail "Pinecone query failed: $(echo "$PSTATS" | tail -1)"
    else
        echo "$PSTATS" | sed 's/^/    /'
    fi
else
    warn "pinecone_stats.py not found — skipping vector count"
fi

# ─── NODE 5: Render API ───────────────────────────────────────
hdr "NODE 5 — RENDER API"

echo "  Pinging $API_URL/health ..."
HTTP_CODE=$(curl -s -o /tmp/fbf_health_resp.txt -w "%{http_code}" --max-time 15 "$API_URL/health" 2>/dev/null)
BODY=$(cat /tmp/fbf_health_resp.txt 2>/dev/null | head -c 200)

if [ "$HTTP_CODE" = "200" ]; then
    ok "API healthy (HTTP 200)"
    echo "    $BODY"
elif [ "$HTTP_CODE" = "000" ]; then
    fail "API unreachable (timeout or DNS failure)"
else
    warn "API returned HTTP $HTTP_CODE: $BODY"
fi

# ─── Recent Pipeline Logs ─────────────────────────────────────
hdr "LAST PIPELINE RUN"

LATEST_LOG=$(ls -t "$LOG_DIR"/pipeline_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    LOG_TIME=$(stat -f %Sm -t "%Y-%m-%d %H:%M" "$LATEST_LOG" 2>/dev/null)
    ok "Last log: $(basename "$LATEST_LOG") ($LOG_TIME)"
    echo ""
    echo "  Last 15 lines:"
    tail -15 "$LATEST_LOG" | sed 's/^/    /'
else
    warn "No pipeline logs found in $LOG_DIR"
fi

# ─── Summary ──────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "  CONTENT TOTALS"
echo "  Channels: $TOTAL_CHANNELS registered, $CHANNELS_WITH_CONTENT with content"
echo "  Transcripts: $TOTAL_TXTS individual | $MASTER_COUNT masters"
echo "  Pending mp3s: $TOTAL_MP3S"
echo "════════════════════════════════════════════"
echo ""
