cd /Users/bryanantonelli/dev/forged-by-freedom/ingest

cat > bulk_channel_builder.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNELS_DIR="$BASE_DIR/channels"
INPUT_FILE="$BASE_DIR/bulk_channels.txt"

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "❌ bulk_channels.txt not found"
  exit 1
fi

echo "=============================================="
echo "📦 Bulk Channel Builder"
echo "📄 Source: bulk_channels.txt"
echo "📂 Target: $CHANNELS_DIR"
echo "=============================================="

CREATED=0
SKIPPED=0

while IFS='|' read -r CATEGORY HANDLE URL; do
  # skip empty lines
  [[ -z "${CATEGORY// }" ]] && continue

  TARGET_DIR="$CHANNELS_DIR/$CATEGORY/$HANDLE"
  CHANNEL_FILE="$TARGET_DIR/channel.url"

  mkdir -p "$TARGET_DIR"

  if [[ -f "$CHANNEL_FILE" ]]; then
    ((SKIPPED+=1))
    continue
  fi

  echo "$URL" > "$CHANNEL_FILE"
  ((CREATED+=1))

done < "$INPUT_FILE"

echo ""
echo "✅ Bulk channel build complete"
echo "➕ Created: $CREATED"
echo "⏭️  Skipped (already existed): $SKIPPED"
echo "=============================================="
EOF
