#!/bin/bash
# --- Universal GitHub uploader for all channels ---

CHANNEL_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNEL_NAME="$(basename "$CHANNEL_DIR")"
REPO_DIR="/Users/weero/thinkbig_podcast/transcripts"
LOG_FILE="$CHANNEL_DIR/github_sync.log"

cd "$REPO_DIR" || exit 1

# Ensure repo exists and remote is correct
if [ ! -d ".git" ]; then
    echo "❌ No Git repo found in $REPO_DIR"
    exit 1
fi

# Stage only this channel’s folder
git pull origin main >> "$LOG_FILE" 2>&1
git add "$CHANNEL_DIR" >> "$LOG_FILE" 2>&1

if ! git diff --cached --quiet; then
    git commit -m "Auto update for $CHANNEL_NAME: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1
    echo "✅ $CHANNEL_NAME synced to GitHub at $(date)" | tee -a "$LOG_FILE"
else
    echo "ℹ️ No changes for $CHANNEL_NAME at $(date)" | tee -a "$LOG_FILE"
fi

#!/bin/bash
# --- Universal GitHub uploader for all channels ---

CHANNEL_DIR="$(cd "$(dirname "$0")" && pwd)"
CHANNEL_NAME="$(basename "$CHANNEL_DIR")"
REPO_DIR="/Users/weero/thinkbig_podcast/transcripts"
LOG_FILE="$CHANNEL_DIR/github_sync.log"

cd "$REPO_DIR" || exit 1

# Ensure repo exists and remote is correct
if [ ! -d ".git" ]; then
    echo "❌ No Git repo found in $REPO_DIR"
    exit 1
fi

# Stage only this channel’s folder
git pull origin main >> "$LOG_FILE" 2>&1
git add "$CHANNEL_DIR" >> "$LOG_FILE" 2>&1

if ! git diff --cached --quiet; then
    git commit -m "Auto update for $CHANNEL_NAME: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1
    echo "✅ $CHANNEL_NAME synced to GitHub at $(date)" | tee -a "$LOG_FILE"
else
    echo "ℹ️ No changes for $CHANNEL_NAME at $(date)" | tee -a "$LOG_FILE"
fi

