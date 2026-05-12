<#
.SYNOPSIS
  Register Windows Scheduled Tasks for the FBF scraper pipeline.

.DESCRIPTION
  Creates two daily tasks under the current user:
    FBF-Scrapers-Daily   at 23:00 (default) - runs Janoshik + MESO-Rx + Reddit scrapers
    FBF-Grade-Monitor    at 23:50 (default) - reads Janoshik DB, emails grade-change alerts to Desktop

  Scrapers run first so the 1 AM FBF-Nightly-Ingest picks up the new .txt files.
  Idempotent - safe to re-run; existing tasks are unregistered first.

  Runtime estimates (first run):
    Janoshik spider : ~45-60 min  (subsequent nights ~10 min, skips known verify keys)
    MESO-Rx spider  : ~15-20 min  (subsequent nights ~5 min, skips existing posts)
    Reddit scraper  : ~25-30 min  (subsequent nights ~5 min, skips existing files)
    Grade monitor   : ~30 sec
    Total first run : ~90 min     (fits comfortably before 1 AM ingest)

.PARAMETER ScraperTime
  Time-of-day for the scraper run, in HH:mm. Default 23:00.

.PARAMETER MonitorTime
  Time-of-day for the grade monitor, in HH:mm. Default 23:50.

.PARAMETER SkipReddit
  If specified, scrapers run without the Reddit step (use if no Reddit API key yet).

.EXAMPLE
  PS> cd C:\Users\Antonelli\forged-by-freedom\ingest\scrapers
  PS> powershell -ExecutionPolicy Bypass -File .\setup_scraper_task.ps1

.EXAMPLE
  PS> .\setup_scraper_task.ps1 -SkipReddit

.EXAMPLE
  PS> .\setup_scraper_task.ps1 -ScraperTime 22:00 -MonitorTime 22:55
#>

[CmdletBinding()]
param(
    [string]$ScraperTime  = '23:00',
    [string]$MonitorTime  = '23:50',
    [switch]$SkipReddit
)

$ErrorActionPreference = 'Stop'

$scraperDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ingestDir   = Split-Path -Parent $scraperDir
$runAll      = Join-Path $scraperDir 'run_all.py'
$gradeMonitor = Join-Path $scraperDir 'vendor_grade_monitor.py'

if (-not (Test-Path $runAll))       { throw "run_all.py not found at $runAll" }
if (-not (Test-Path $gradeMonitor)) { throw "vendor_grade_monitor.py not found at $gradeMonitor" }

# --- Locate Python in the ingest venv (preferred) or system Python -----
$venvPy = Join-Path $ingestDir '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    $pythonExe = $venvPy
} else {
    $pythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) {
        throw "python.exe not found. Activate the ingest venv or install Python."
    }
}

Write-Host "python   : $pythonExe"
Write-Host "run_all  : $runAll"
Write-Host "monitor  : $gradeMonitor"
Write-Host "scrapers : daily @ $ScraperTime"
Write-Host "monitor  : daily @ $MonitorTime"
if ($SkipReddit) { Write-Host "reddit   : SKIPPED (--skip-reddit)" }
Write-Host ""

# --- Log directory ---------------------------------------------------
$logDir = Join-Path $scraperDir 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# --- Common settings -------------------------------------------------
$commonSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

# --- Task 1: Scrapers ------------------------------------------------
# Wrap in a cmd /c so we can redirect stdout+stderr to a dated log file.
# PowerShell -Command is used to build the log filename dynamically.
$scraperArgs = if ($SkipReddit) { '--skip-reddit' } else { '' }

# Build a cmd wrapper that logs to scrapers\logs\scrapers_YYYYMMDD.log
$scraperCmd = @"
/c "$pythonExe" "$runAll" $scraperArgs >> "$logDir\scrapers_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.log" 2>&1
"@

$scraperAction = New-ScheduledTaskAction `
    -Execute 'cmd.exe' `
    -Argument $scraperCmd.Trim() `
    -WorkingDirectory $scraperDir

$scraperTrigger = New-ScheduledTaskTrigger -Daily -At $ScraperTime

Get-ScheduledTask -TaskName 'FBF-Scrapers-Daily' -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName    'FBF-Scrapers-Daily' `
    -Description 'Forged By Freedom - nightly Janoshik + MESO-Rx + Reddit scrapers' `
    -Action      $scraperAction `
    -Trigger     $scraperTrigger `
    -Settings    $commonSettings `
    -Principal   $principal | Out-Null

Write-Host "[OK] Registered: FBF-Scrapers-Daily @ $ScraperTime"

# --- Task 2: Grade monitor -------------------------------------------
$monitorCmd = @"
/c "$pythonExe" "$gradeMonitor" >> "$logDir\grade_monitor_%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.log" 2>&1
"@

$monitorAction = New-ScheduledTaskAction `
    -Execute 'cmd.exe' `
    -Argument $monitorCmd.Trim() `
    -WorkingDirectory $scraperDir

$monitorTrigger = New-ScheduledTaskTrigger -Daily -At $MonitorTime

Get-ScheduledTask -TaskName 'FBF-Grade-Monitor' -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName    'FBF-Grade-Monitor' `
    -Description 'Forged By Freedom - vendor grade change monitor, writes HTML delta to Desktop' `
    -Action      $monitorAction `
    -Trigger     $monitorTrigger `
    -Settings    $commonSettings `
    -Principal   $principal | Out-Null

Write-Host "[OK] Registered: FBF-Grade-Monitor @ $MonitorTime"

# --- Summary ---------------------------------------------------------
Write-Host ""
Write-Host "Daily schedule:"
Write-Host "  $ScraperTime  FBF-Scrapers-Daily   (Janoshik + MESO-Rx + Reddit)"
Write-Host "  $MonitorTime  FBF-Grade-Monitor    (vendor grade delta report -> Desktop)"
Write-Host "  01:00  FBF-Nightly-Ingest  (existing - picks up new .txt into Chroma)"
Write-Host "  08:00  FBF-Health-Check    (existing)"
Write-Host ""
Write-Host "Logs saved to: $logDir"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  View tasks:          Get-ScheduledTask FBF-*"
Write-Host "  Run scrapers now:    Start-ScheduledTask -TaskName FBF-Scrapers-Daily"
Write-Host "  Run monitor now:     Start-ScheduledTask -TaskName FBF-Grade-Monitor"
Write-Host "  Test without Reddit: .\setup_scraper_task.ps1 -SkipReddit"
Write-Host ""
Write-Host "Reddit setup (if not done yet):"
Write-Host "  1. Go to: https://www.reddit.com/prefs/apps"
Write-Host "  2. Click 'create another app' (bottom of page)"
Write-Host "  3. Name: FBF-RAG  |  Type: script  |  Redirect: http://localhost:8080"
Write-Host "  4. Copy client ID (under app name) + secret"
Write-Host "  5. Edit: $scraperDir\.env"
Write-Host "     REDDIT_CLIENT_ID=your_id_here"
Write-Host "     REDDIT_CLIENT_SECRET=your_secret_here"
Write-Host "     REDDIT_USER_AGENT=FBF-RAG-Scraper/1.0"
