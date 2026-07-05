#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# ECHO — one-shot installer for macOS and Linux
#
# Usage:   bash install.sh
#
# What it does:
#   1. Verifies Python 3.10+ (installs via Homebrew/apt if missing)
#   2. Verifies ffmpeg (installs via Homebrew/apt if missing)
#   3. Creates a Python virtualenv at ./.venv
#   4. Installs ECHO dependencies into the venv
#   5. Smoke-tests the install (imports the core modules)
#   6. Prints how to run the dashboards
# ──────────────────────────────────────────────────────────────────
set -u

note()   { printf "\n\033[1;34m▶ %s\033[0m\n" "$*"; }
ok()     { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn()   { printf "  \033[1;33m!\033[0m %s\n" "$*"; }
fail()   { printf "  \033[1;31m✗\033[0m %s\n" "$*"; exit 1; }

OS=$(uname -s)

# ── 1. Python 3.10+ ──────────────────────────────────────────────
note "Checking Python"
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver=$("$candidate" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')")
    major=${ver%.*}; minor=${ver#*.}
    if [ "$major" = "3" ] && [ "$minor" -ge 10 ]; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    warn "No Python 3.10+ found. Installing via brew…"
    brew install python@3.12 || fail "brew install python@3.12 failed"
    PYTHON_BIN="python3.12"
  elif command -v apt-get >/dev/null 2>&1; then
    warn "No Python 3.10+ found. Installing via apt…"
    sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip python3-venv \
      || fail "apt install python3 failed (need sudo)"
    PYTHON_BIN="python3"
  else
    fail "No Python 3.10+ found and no supported package manager. Install Python 3.10+ from python.org and re-run."
  fi
fi
ok "Python: $PYTHON_BIN ($($PYTHON_BIN --version))"

# ── 2. ffmpeg ───────────────────────────────────────────────────
note "Checking ffmpeg"
if ! command -v ffmpeg >/dev/null 2>&1; then
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    warn "ffmpeg not found. Installing via brew…"
    brew install ffmpeg || fail "brew install ffmpeg failed"
  elif command -v apt-get >/dev/null 2>&1; then
    warn "ffmpeg not found. Installing via apt…"
    sudo apt-get install -y -qq ffmpeg || fail "apt install ffmpeg failed (need sudo)"
  else
    fail "ffmpeg not found and no supported package manager. Install ffmpeg manually and re-run."
  fi
fi
ok "ffmpeg: $(ffmpeg -version | head -1 | awk '{print $1, $2, $3}')"

# ── 3. virtualenv + pip install ─────────────────────────────────
note "Creating virtualenv at ./.venv"
"$PYTHON_BIN" -m venv .venv || fail "venv creation failed"
ok "virtualenv ready"

note "Installing Python dependencies"
./.venv/bin/pip install --quiet --upgrade pip 2>&1 | tail -1
./.venv/bin/pip install --quiet -r requirements.txt 2>&1 | tail -1 \
  && ok "dependencies installed" || fail "pip install failed"

# ── 4. Smoke test ───────────────────────────────────────────────
note "Smoke-testing"
./.venv/bin/python -c "
import echo_engine, echo_ml, echo_rtsp, echo_zones, echo_correlation
import echo_multi, echo_correlation_dashboard
import echo_alerts, echo_dashboard
import echo_vision, echo_face, echo_dedrone, echo_flock
import echo_dmv_sc, echo_cellebrite, echo_drone_forensics
import echo_viapath, echo_tecore
import yaml
yaml.safe_load(open('echo_cameras.yaml'))
print('  all modules import cleanly')
print('  config YAML loads')
" 2>&1 | tail -3

# ── 5. Done ─────────────────────────────────────────────────────
cat <<'EOF'

────────────────────────────────────────────────────────────────────
  ECHO is installed.

  Activate the venv:
      source .venv/bin/activate

  Then run any of:

  • Single-mic acoustic dashboard (original ECHO, no cameras needed):
      python echo_dashboard.py
      → http://127.0.0.1:5050

  • Correlation dashboard in DEMO mode (no real data needed):
      python echo_correlation_dashboard.py --demo --port 5060
      → http://127.0.0.1:5060

  • Full multi-camera orchestrator (requires editing
    echo_cameras.yaml with real RTSP URLs first):
      python echo_multi.py --config echo_cameras.yaml

  Open INTEGRATION_CHECKLIST.md for the next-steps document to send
  to the committee. They fill in the blanks → vendor integrations
  light up.
────────────────────────────────────────────────────────────────────
EOF
