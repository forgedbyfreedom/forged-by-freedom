#!/bin/bash
# =========================================================
# 💪  Forged By Freedom — AI Transcript Processing Pipeline
# =========================================================

set -e  # Stop on first error

# === COLORS ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # No Color

echo ""
echo "==============================================="
echo -e "${BLUE}💪  Forged By Freedom AI Processing Sequence${NC}"
echo "==============================================="
echo ""

# === PATHS ===
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$(find "$PROJECT_DIR" -maxdepth 1 -type d -name '.venv*' | head -n 1)/bin/activate"

# === Activate Virtual Environment ===
if [ -f "$VENV_DIR" ]; then
  echo -e "${YELLOW}⚙️  Activating virtual environment...${NC}"
  source "$VENV_DIR"
else
  echo -e "${RED}❌ Could not find a virtual environment in $PROJECT_DIR${NC}"
  echo -e "${YELLOW}💡 Tip: Create one using:${NC} python3 -m venv .venv311"
  exit 1
fi

# === Load .env ===
if [ -f "$PROJECT_DIR/.env" ]; then
  echo -e "${GREEN}🌿 Loading environment variables from .env...${NC}"
  export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
else
  echo -e "${YELLOW}⚠️  No .env file found — continuing without environment vars${NC}"
fi

cd "$PROJECT_DIR"

# === Step 1: Split Transcripts ===
echo ""
echo -e "${BLUE}▶️  Step 1: Splitting transcripts by episode...${NC}"
if python3 split_transcripts_by_episode.py; then
  echo -e "${GREEN}✅ Step 1 completed successfully.${NC}"
else
  echo -e "${RED}❌ Step 1 failed.${NC}"
  exit 1
fi

# === Step 2: Index Transcripts ===
echo ""
echo -e "${BLUE}▶️  Step 2: Indexing transcripts to Pinecone...${NC}"
if [ -z "$PINECONE_API_KEY" ]; then
  echo -e "${YELLOW}⚠️  Skipping indexing — Pinecone API key not found.${NC}"
else
  if python3 index_transcripts.py; then
    echo -e "${GREEN}✅ Step 2 completed successfully.${NC}"
  else
    echo -e "${RED}❌ Step 2 failed.${NC}"
  fi
fi

# === Step 3: Analyze Transcripts ===
echo ""
echo -e "${BLUE}▶️  Step 3: Analyzing transcript stats...${NC}"
if python3 analyze_transcripts.py; then
  echo -e "${GREEN}✅ Step 3 completed successfully.${NC}"
else
  echo -e "${RED}❌ Step 3 failed.${NC}"
fi

# === Step 4: Launch Flask App ===
echo ""
echo -e "${BLUE}▶️  Step 4: Launching Flask search interface...${NC}"
if python3 app.py; then
  echo -e "${GREEN}✅ App launched successfully.${NC}"
else
  echo -e "${RED}❌ Failed to start app.${NC}"
fi

echo ""
echo -e "${GREEN}🎯 All pipeline steps completed.${NC}"
