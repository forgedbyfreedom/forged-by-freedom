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

# ─── CUDA / PyTorch ──────────────────────────────────────────
echo ""
echo "Checking for NVIDIA GPU..."
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1)
    echo "✅ NVIDIA GPU detected: $GPU_NAME ($VRAM)"
    echo "   Installing PyTorch with CUDA 12.1 support..."
    "$PIP" install -q torch --index-url https://download.pytorch.org/whl/cu121
    echo "✅ PyTorch + CUDA installed"
    echo "   Installing CTranslate2 CUDA build (faster-whisper backend)..."
    "$PIP" install -q ctranslate2
else
    echo "⚠️  No NVIDIA GPU detected — transcription will use CPU (int8, slower)"
    echo "   If you have a GPU, install NVIDIA drivers first then re-run setup"
fi

echo "✅ All dependencies installed"

# ─── Verify GPU + whisper backend ────────────────────────────
echo ""
echo "Verifying GPU and whisper backend..."
"$VENV_PYTHON" -c "
import platform
is_apple = platform.system() == 'Darwin' and platform.machine() == 'arm64'
if is_apple:
    print('  Platform: Apple Silicon → using MLX Whisper')
    exit()

try:
    import torch
    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f'  ✅ CUDA GPU: {gpu} ({vram:.0f}GB VRAM)')
        print(f'  ✅ Transcription: faster-whisper large-v3 @ float16 (FAST)')
        if vram >= 20:
            print(f'  ✅ VRAM is sufficient for large-v3 — full quality')
        else:
            print(f'  ⚠️  VRAM <20GB — consider medium model if OOM errors occur')
    else:
        print('  ⚠️  No CUDA — will use CPU with int8')
except ImportError:
    print('  ⚠️  torch not found — faster-whisper will auto-detect (slower)')

from faster_whisper import WhisperModel
print('  ✅ faster-whisper imported OK')
" 2>/dev/null || echo "⚠️  GPU check failed — check CUDA/driver installation"

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
