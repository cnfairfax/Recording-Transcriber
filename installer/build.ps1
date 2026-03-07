<#
.SYNOPSIS
    Build the Recording Transcriber installer.

.DESCRIPTION
    Runs PyInstaller to bundle the application, then runs Inno Setup to produce
    a single-file .exe installer.

    Output files
    ------------
    dist\Recording Transcriber\       – unpacked app (from PyInstaller)
    dist\installer\RecordingTranscriber-*-Setup.exe  – final installer

.PARAMETER SkipPyInstaller
    Skip the PyInstaller step (use the existing dist\Recording Transcriber\ folder).

.PARAMETER SkipInnoSetup
    Skip the Inno Setup step (only run PyInstaller).

.PARAMETER InnoSetupPath
    Path to ISCC.exe.  Defaults to the standard Inno Setup 6 install location.

.EXAMPLE
    # Full build from the repo root:
    .\installer\build.ps1

    # Re-run only Inno Setup after tweaking installer.iss:
    .\installer\build.ps1 -SkipPyInstaller

    # Run only PyInstaller (test bundling without producing an installer):
    .\installer\build.ps1 -SkipInnoSetup

.NOTES
    Requires:
      - Python venv at .venv\ with faster-whisper, openvino, PyQt6, pyinstaller
      - Inno Setup 6  https://jrsoftware.org/isdl.php
#>
[CmdletBinding()]
param(
    [switch]$SkipPyInstaller,
    [switch]$SkipInnoSetup,
    [string]$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"

# ── Locate repository root ────────────────────────────────────────────────────
$Root = Split-Path -Parent $PSScriptRoot   # script lives in installer\, root is one up
Set-Location $Root
Write-Host "Repository root : $Root" -ForegroundColor DarkGray

# ── Helpers ───────────────────────────────────────────────────────────────────
function Step([string]$msg) {
    Write-Host "`n$('─' * 72)" -ForegroundColor DarkGray
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "$('─' * 72)" -ForegroundColor DarkGray
}

function Require-File([string]$path, [string]$hint) {
    if (-not (Test-Path $path)) {
        Write-Error "Required file not found: $path`n$hint"
        exit 1
    }
}

# ── Verify prerequisites ──────────────────────────────────────────────────────
Require-File ".venv\Scripts\python.exe"      "Run:  python -m venv .venv  then  pip install -r requirements.txt pyinstaller"
Require-File "installer\recording_transcriber.spec" "Spec file missing from installer\"
Require-File "installer\installer.iss"       "Inno Setup script missing from installer\"

# ── Ensure PyInstaller is installed ───────────────────────────────────────────
$pyinstallerCheck = & ".venv\Scripts\python.exe" -c "import PyInstaller; print(PyInstaller.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Step "Installing PyInstaller into venv..."
    & ".venv\Scripts\pip.exe" install pyinstaller
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install pyinstaller failed"; exit 1 }
} else {
    Write-Host "PyInstaller $pyinstallerCheck found." -ForegroundColor DarkGray
}

# ── Step 1: PyInstaller ───────────────────────────────────────────────────────
if (-not $SkipPyInstaller) {
    Step "Running PyInstaller..."

    & ".venv\Scripts\python.exe" -m PyInstaller `
        installer\recording_transcriber.spec `
        --noconfirm `
        --log-level WARN 2>&1 | ForEach-Object {
            # PyInstaller writes INFO/WARNING to stderr.  PowerShell would turn
            # those into ErrorRecord objects and abort the script (due to
            # $ErrorActionPreference = "Stop") even when PyInstaller exits 0.
            # Printing them ourselves keeps $LASTEXITCODE accurate.
            Write-Host $_
        }

    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller exited with code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    $appDir = "dist\Recording Transcriber"
    if (-not (Test-Path $appDir)) {
        Write-Error "PyInstaller did not produce: $appDir"
        exit 1
    }

    $mainExe  = "$appDir\Recording Transcriber.exe"
    $dlExe    = "$appDir\download_model.exe"

    Require-File $mainExe  "PyInstaller build seems incomplete — Recording Transcriber.exe not found"
    Require-File $dlExe    "PyInstaller build seems incomplete — download_model.exe not found"

    $mainSize = [math]::Round((Get-Item $mainExe).Length / 1MB, 1)
    $dlSize   = [math]::Round((Get-Item $dlExe).Length   / 1MB, 1)
    Write-Host "Recording Transcriber.exe  ${mainSize} MB" -ForegroundColor Green
    Write-Host "download_model.exe         ${dlSize} MB"   -ForegroundColor Green
    Write-Host "PyInstaller step complete." -ForegroundColor Green
} else {
    Write-Host "(Skipping PyInstaller)" -ForegroundColor DarkGray
    Require-File "dist\Recording Transcriber\Recording Transcriber.exe" `
        "Run without -SkipPyInstaller first to produce a dist\ folder."
}

# ── Step 2: Inno Setup ────────────────────────────────────────────────────────
if (-not $SkipInnoSetup) {
    Step "Running Inno Setup..."

    if (-not (Test-Path $InnoSetupPath)) {
        Write-Warning @"
Inno Setup not found at: $InnoSetupPath

Download and install Inno Setup 6 from:
  https://jrsoftware.org/isdl.php

Then re-run:
  .\installer\build.ps1 -SkipPyInstaller

Or pass the correct path:
  .\installer\build.ps1 -SkipPyInstaller -InnoSetupPath 'C:\...\ISCC.exe'
"@
        exit 1
    }

    New-Item -ItemType Directory -Path "dist\installer" -Force | Out-Null

    & $InnoSetupPath "installer\installer.iss"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Inno Setup exited with code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    $installers = Get-ChildItem "dist\installer\*.exe" | Sort-Object LastWriteTime -Descending
    if ($installers) {
        $latest = $installers[0]
        $sizeMB = [math]::Round($latest.Length / 1MB, 0)
        Write-Host "Installer created: $($latest.Name)  ($sizeMB MB)" -ForegroundColor Green
        Write-Host "Full path: $($latest.FullName)" -ForegroundColor Green
    }

    Write-Host "Inno Setup step complete." -ForegroundColor Green
} else {
    Write-Host "(Skipping Inno Setup)" -ForegroundColor DarkGray
}

Write-Host "`nAll steps complete." -ForegroundColor Green
