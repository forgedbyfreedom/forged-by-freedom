#!/bin/bash
# ─────────────────────────────────────────────────────────────
# FBF PIPELINE — PC / WSL SETUP
# ─────────────────────────────────────────────────────────────
# Run once on Windows (via WSL2 or Git Bash) to set up the
# ingest pipeline. Uses faster-whisper instead of MLX Whisper.
#
# Prerequisites:
#   - WSL2 with Ubuntu (recommended) OR Git Bash
#   - Python 3.10-3.12 installed
#   - ffmpeg: sudo apt install ffmpeg  (WSL) or choco install ffmpeg (Windows)
#   - git clone of forgedbyfreedom/forged-by-freedom
#   - .env file with PINECONE_API_KEY, OPENAI_API_KEY, etc.
#
# Usage:
#   cd ingest && bash setup_pc.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "════════════════════════════════════════════"
echo "  FBF PIPELINE — PC SETUP"
echo "════════════════════════════════════════════"
echo ""

# ─── Python check ────────────────────────────────────────────
PYTHON=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)
if [ -z "$PYTHON" ]; then
    echo "❌ Python 3.10-3.12 required. Install via: sudo apt install python3.12 python3.12-venv"
    exit 1
fi
PY_VER=$("$PYTHON" --version)
echo "✅ Python: $PY_VER at $PYTHON"

# ─── ffmpeg check ────────────────────────────────────────────
if command -v ffmpeg >/dev/null 2>&1; then
    echo "✅ ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "⚠️  ffmpeg not found. Installing..."
    if command -v apt >/dev/null 2>&1; then
        sudo apt install -y ffmpeg
    else
        echo "❌ Install ffmpeg manually: https://ffmpeg.org/download.html"
        exit 1
    fi
fi

# ─── Create venv ─────────────────────────────────────────────
VENV="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo ""
    echo "Creating virtual environment..."
    "$PYTHON" -m venv "$VENV"
    echo "✅ venv created"
else
    echo "✅ venv already exists"
fi

PIP="$VENV/bin/pip"
VENV_PYTHON="$VENV/bin/python3"

# ─── Install dependencies ────────────────────────────────────
echo ""
echo "Installing pipeline dependencies..."
"$PIP" install --upgrade pip -q

# Core pipeline deps
"$PIP" install -q \
    pinecone \
    openai \
    tiktoken \
    python-dotenv \
    requests \
    yt-dlp

# faster-whisper for PC (GPU if available, CPU fallback)
echo "Installing faster-whisper (PC transcription backend)..."
"$PIP" install -q faster-whisper

echo "✅ All dependencies installed"

# ─── Verify whisper backend ──────────────────────────────────
echo ""
echo "Verifying whisper_transcribe.py backend detection..."
"$VENV_PYTHON" -c "
import platform
is_apple = platform.system() == 'Darwin' and platform.machine() == 'arm64'
if is_apple:
    print('  Platform: Apple Silicon → using MLX Whisper')
else:
    from faster_whisper import WhisperModel
    print('  Platform: PC/Linux → using faster-whisper ✅')
"

# ─── GPU check ───────────────────────────────────────────────
echo ""
"$VENV_PYTHON" -c "
try:
    import torch
    if torch.cuda.is_available():
        print('✅ CUDA GPU detected:', torch.cuda.get_device_name(0))
        print('   Transcription will use GPU (fast)')
    else:
        print('⚠️  No CUDA GPU — will use CPU (slower but works)')
except ImportError:
    print('⚠️  torch not installed — faster-whisper will auto-detect device')
" 2>/dev/null || echo "⚠️  torch not found — faster-whisper handles device detection automatically"

# ─── .env check ──────────────────────────────────────────────
echo ""
ENV_FILE="$SCRIPT_DIR/../.env"
if [ -f "$ENV_FILE" ]; then
    echo "✅ .env found"
    grep -q "PINECONE_API_KEY" "$ENV_FILE" && echo "  ✅ PINECONE_API_KEY set" || echo "  ❌ PINECONE_API_KEY missing"
    grep -q "OPENAI_API_KEY" "$ENV_FILE" && echo "  ✅ OPENAI_API_KEY set" || echo "  ❌ OPENAI_API_KEY missing"
else
    echo "❌ .env not found at $ENV_FILE"
    echo "   Copy .env from Mac or create it with your API keys"
fi

# ─── yt-dlp check ────────────────────────────────────────────
echo ""
YT_DLP="$VENV/bin/yt-dlp"
if [ -x "$YT_DLP" ]; then
    echo "✅ yt-dlp $("$YT_DLP" --version)"
else
    echo "❌ yt-dlp not found in venv"
fi

echo ""
echo "════════════════════════════════════════════"
echo "  SETUP COMPLETE"
echo ""
echo "  Next steps:"
echo "  1. Copy .env from Mac (has your API keys)"
echo "  2. git pull  (get latest transcripts from Mac)"
echo "  3. ./pipeline.sh download   (download new content)"
echo "  4. ./pipeline.sh transcribe (transcribe with faster-whisper)"
echo "  5. ./pipeline.sh ingest     (push to Pinecone)"
echo "  6. git add -A && git commit -m 'pc transcripts' && git push"
echo "════════════════════════════════════════════"
echo ""
