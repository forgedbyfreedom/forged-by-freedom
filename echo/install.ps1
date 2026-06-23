# ──────────────────────────────────────────────────────────────────
# ECHO — one-shot installer for Windows (PowerShell)
#
# Usage:   Right-click → Run with PowerShell
#          OR from a PowerShell window:
#              cd <path-to-echo>
#              powershell -ExecutionPolicy Bypass -File install.ps1
#
# What it does:
#   1. Verifies Python 3.10+ (installs via winget if missing)
#   2. Verifies ffmpeg (installs via winget if missing)
#   3. Creates a Python virtualenv at .\.venv
#   4. Installs ECHO dependencies into the venv
#   5. Smoke-tests the install
#   6. Prints how to run the dashboards
# ──────────────────────────────────────────────────────────────────

$ErrorActionPreference = 'Stop'

function Note($msg)  { Write-Host "`n[*] $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "    + $msg"  -ForegroundColor Green }
function Warn($msg)  { Write-Host "    ! $msg"  -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "    x $msg"  -ForegroundColor Red; exit 1 }

# ── 1. Python 3.10+ ─────────────────────────────────────────────
Note "Checking Python"
$pythonBin = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    try {
        $ver = & $candidate -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($ver) {
            $major, $minor = $ver.Split('.')
            if ([int]$major -eq 3 -and [int]$minor -ge 10) {
                $pythonBin = $candidate
                break
            }
        }
    } catch {}
}
if (-not $pythonBin) {
    Warn "No Python 3.10+ found. Installing via winget…"
    winget install -e --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Fail "winget install Python failed" }
    Warn "You may need to close + reopen PowerShell so the new Python is on PATH. Then re-run install.ps1."
    exit 0
}
Ok "Python: $pythonBin ($(& $pythonBin --version))"

# ── 2. ffmpeg ───────────────────────────────────────────────────
Note "Checking ffmpeg"
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Warn "ffmpeg not found. Installing via winget…"
    winget install -e --id Gyan.FFmpeg --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Fail "winget install ffmpeg failed" }
    Warn "Close + reopen PowerShell so ffmpeg is on PATH, then re-run install.ps1."
    exit 0
}
$ffver = (ffmpeg -version | Select-Object -First 1)
Ok "ffmpeg: $ffver"

# ── 3. virtualenv + pip install ─────────────────────────────────
Note "Creating virtualenv at .\.venv"
& $pythonBin -m venv .venv
if (-not (Test-Path '.\.venv\Scripts\pip.exe')) { Fail "venv creation failed" }
Ok "virtualenv ready"

Note "Installing Python dependencies"
& .\.venv\Scripts\pip install --quiet --upgrade pip
& .\.venv\Scripts\pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed" }
Ok "dependencies installed"

# ── 4. Smoke test ───────────────────────────────────────────────
Note "Smoke-testing"
& .\.venv\Scripts\python -c @"
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
"@

# ── 5. Done ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "────────────────────────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host "  ECHO is installed."  -ForegroundColor Green
Write-Host ""
Write-Host "  Activate the venv:"
Write-Host "      .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "  Then run any of:"
Write-Host ""
Write-Host "  - Single-mic acoustic dashboard:"
Write-Host "      python echo_dashboard.py"
Write-Host "      -> http://127.0.0.1:5050"
Write-Host ""
Write-Host "  - Correlation dashboard in DEMO mode:"
Write-Host "      python echo_correlation_dashboard.py --demo --port 5060"
Write-Host "      -> http://127.0.0.1:5060"
Write-Host ""
Write-Host "  - Full multi-camera orchestrator (edit echo_cameras.yaml first):"
Write-Host "      python echo_multi.py --config echo_cameras.yaml"
Write-Host ""
Write-Host "  Send INTEGRATION_CHECKLIST.md to the committee for vendor wiring."
Write-Host "────────────────────────────────────────────────────────────────────" -ForegroundColor Cyan
