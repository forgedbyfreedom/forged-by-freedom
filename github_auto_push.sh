#!/bin/bash
# ===============================================
# Forged by Freedom – Think Big Auto Uploader
# ===============================================

# CONFIG
REPO_DIR="/Users/weero/thinkbig_podcast/transcripts/@ThinkBIGBodybuilding"
BRANCH="main"
LOG_FILE="$REPO_DIR/github_sync.log"

cd "$REPO_DIR" || { echo "❌ Repo not found"; exit 1; }

# Pull latest changes to avoid merge conflicts
git pull origin $BRANCH >> "$LOG_FILE" 2>&1

# Stage and commit updates
git add -A
if ! git diff --cached --quiet; then
    git commit -m "Auto update: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE" 2>&1
    git push https://github.com/forgedbyfreedom/thinkbig-transcripts.git $BRANCH >> "$LOG_FILE" 2>&1
    echo "✅ Synced with GitHub at $(date)" >> "$LOG_FILE"
else
    echo "ℹ️ No changes to push at $(date)" >> "$LOG_FILE"
fi

