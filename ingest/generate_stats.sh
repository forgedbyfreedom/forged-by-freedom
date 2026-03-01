#!/bin/bash
# ─────────────────────────────────────────────────────────────
# generate_stats.sh — Count transcripts, words, channels
# and push to the Render API /update-stats endpoint
# Called by pipeline.sh at the end of each nightly run
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$SCRIPT_DIR/channels"
API_URL="${FBF_API_URL:-https://forged-by-freedom-api-nm4f.onrender.com}"
STATS_KEY="${STATS_UPDATE_KEY:-}"

echo "📊 Generating stats..."

# Count transcripts (all .txt files except channel.url)
TRANSCRIPTS=$(find "$CHANNELS_DIR" -name "*.txt" -not -name "channel.url" | wc -l | tr -d ' ')

# Count words across all transcripts
WORDS=$(find "$CHANNELS_DIR" -name "*.txt" -not -name "channel.url" -print0 | xargs -0 wc -w 2>/dev/null | grep " total$" | awk '{sum += $1} END {print sum}')
[ -z "$WORDS" ] && WORDS=0

# Count channels with content
CHANNELS=$(find "$CHANNELS_DIR" -mindepth 1 -maxdepth 1 -type d | while read -r d; do
  tc=$(find "$d" -name "*.txt" -not -name "channel.url" 2>/dev/null | wc -l | tr -d ' ')
  [ "$tc" -gt "0" ] && echo "$tc"
done | wc -l | tr -d ' ')

echo "  Transcripts: $TRANSCRIPTS"
echo "  Words: $WORDS"
echo "  Channels with content: $CHANNELS"

# Write local stats file
cat > "$SCRIPT_DIR/stats.json" <<EOF
{
  "transcripts": $TRANSCRIPTS,
  "words": $WORDS,
  "channels": $CHANNELS,
  "lastUpdated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "  Written to $SCRIPT_DIR/stats.json"

# Push to API if URL is set
if [ -n "$API_URL" ]; then
  HEADERS=(-H "Content-Type: application/json")
  [ -n "$STATS_KEY" ] && HEADERS+=(-H "X-Stats-Key: $STATS_KEY")

  RESPONSE=$(curl -s -X POST "$API_URL/update-stats" \
    "${HEADERS[@]}" \
    -d "{\"transcripts\":$TRANSCRIPTS,\"words\":$WORDS,\"channels\":$CHANNELS}" \
    --max-time 10 2>&1)

  if echo "$RESPONSE" | grep -q '"ok"'; then
    echo "  Pushed to API"
  else
    echo "  API push failed (server may be cold): $RESPONSE"
  fi
fi

echo "✅ Stats generation complete"
