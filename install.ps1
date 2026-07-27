# IRIS AI PowerShell One-Step Installer for Windows
# Usage: Right-click → "Run with PowerShell"  OR  powershell -ExecutionPolicy Bypass -File install.ps1
# Idempotent — safe to run multiple times.

#Requires -Version 5.1
Set-StrictMode -Off

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # Suppress Invoke-WebRequest progress bars

# ─────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────
$IRIS_VERSION   = "v3.8.4-RELEASE"
$REPO_URL       = "https://github.com/YOUR_USERNAME/IRIS-AI.git"
$MIN_PY_MAJOR   = 3
$MIN_PY_MINOR   = 9
$VENV_DIR       = ".venv"
$LOG_FILE       = "iris_install.log"
$SCRIPT_DIR     = $PSScriptRoot
if (-not $SCRIPT_DIR) { $SCRIPT_DIR = (Get-Location).Path }

# ─────────────────────────────────────────────────────────────────
#  ANSI COLOURS  (Windows 10+)
# ─────────────────────────────────────────────────────────────────
$ESC   = [char]27
$RESET = "$ESC[0m"
$BOLD  = "$ESC[1m"
$DIM   = "$ESC[2m"
$GREEN = "$ESC[92m"
$CYAN  = "$ESC[96m"
$YELLOW= "$ESC[93m"
$RED   = "$ESC[91m"
$WHITE = "$ESC[97m"

# Enable Virtual Terminal Processing so ANSI codes render in older hosts
try {
    $k32 = Add-Type -MemberDefinition @"
[DllImport("kernel32.dll")] public static extern bool SetConsoleMode(IntPtr h, int m);
[DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int n);
"@ -Name "K32" -Namespace "Win32" -PassThru
    $handle = $k32::GetStdHandle(-11)
    $k32::SetConsoleMode($handle, 7) | Out-Null
} catch {}

# ─────────────────────────────────────────────────────────────────
#  LOG HELPERS
# ─────────────────────────────────────────────────────────────────
$LogLines = [System.Collections.Generic.List[string]]::new()

function LogWrite([string]$msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogLines.Add("[$ts] $msg") | Out-Null
}

function FlushLog {
    try { $LogLines | Set-Content -Path (Join-Path $SCRIPT_DIR $LOG_FILE) -Encoding UTF8 }
    catch {}
}

function Ok([string]$msg) {
    Write-Host "  ${GREEN}[OK]${RESET}  $msg"
    LogWrite "OK    : $msg"
}
function Skip([string]$msg) {
    Write-Host "  ${CYAN}[--]${RESET}  ${DIM}${msg}${RESET}"
    LogWrite "SKIP  : $msg"
}
function Info([string]$msg) {
    Write-Host "  ${CYAN}[..]${RESET}  $msg"
    LogWrite "INFO  : $msg"
}
function Warn([string]$msg) {
    Write-Host "  ${YELLOW}[!!]${RESET}  ${YELLOW}${msg}${RESET}"
    LogWrite "WARN  : $msg"
}
function Step([string]$title) {
    $line = "-" * ($title.Length + 4)
    Write-Host ""
    Write-Host "  ${BOLD}${CYAN}${title}${RESET}"
    Write-Host "  ${DIM}${line}${RESET}"
    LogWrite ""
    LogWrite "---- $title ----"
}
function Fail([string]$msg, [string]$hint = "") {
    Write-Host ""
    Write-Host "  ${RED}${BOLD}[FAILED]  INSTALLATION FAILED${RESET}"
    Write-Host "  ${RED}Reason : $msg${RESET}"
    if ($hint) { Write-Host "  ${YELLOW}Fix    : $hint${RESET}" }
    LogWrite "FAILED: $msg"
    if ($hint) { LogWrite "FIX   : $hint" }
    FlushLog
    Read-Host "Press Enter to close"
    exit 1
}

function Banner {
    Write-Host "${BOLD}${CYAN}"
    Write-Host "   ___ ____  ___ ____      _    ___ "
    Write-Host "  |_ _|  _ \|_ _/ ___|    / \  |_ _|"
    Write-Host "   | || |_) || |\___ \   / _ \  | | "
    Write-Host "   | ||  _ < | | ___) | / ___ \ | | "
    Write-Host "  |___|_| \_\___|____/ /_/   \_\___|"
    Write-Host "${RESET}"
    Write-Host "  ${BOLD}IRIS AI -- Jarvis Terminal Interface${RESET}  ${DIM}${IRIS_VERSION}${RESET}"
    Write-Host "  ${DIM}One-step installer  *  Windows  *  Python 3.9+${RESET}"
    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────
#  STEP 1 — Python
# ─────────────────────────────────────────────────────────────────
function Step-Python {
    Step "Step 1 · Verifying Python version"

    # Locate python executable — try py launcher first (preferred on Windows)
    $pyCmd = $null
    $pyVer = $null

    foreach ($candidate in @("py", "python", "python3")) {
        try {
            $out = & $candidate --version 2>&1 | Out-String
            if ($out -match "Python (\d+)\.(\d+)\.(\d+)") {
                $maj = [int]$Matches[1]
                $min = [int]$Matches[2]
                $pat = [int]$Matches[3]
                if ($maj -ge $MIN_PY_MAJOR -and $min -ge $MIN_PY_MINOR) {
                    $pyCmd = $candidate
                    $pyVer = "$maj.$min.$pat"
                    break
                }
            }
        } catch {}
    }

    if (-not $pyCmd) {
        Fail `
            "Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ not found or not in PATH." `
            "Download Python from https://www.python.org/downloads/ and ensure 'Add to PATH' is checked."
    }

    Info "Using Python command: $pyCmd  ($pyVer)"
    $script:PY = $pyCmd
    Ok "Python $pyVer — compatible"
}

# ─────────────────────────────────────────────────────────────────
#  STEP 2 — Git
# ─────────────────────────────────────────────────────────────────
function Step-Git {
    Step "Step 2 · Checking Git"
    try {
        $ver = & git --version 2>&1 | Out-String
        Ok "Git detected — $($ver.Trim())"
    } catch {
        Warn "Git not found. Git is optional but recommended for future updates."
        Info "Install from: https://git-scm.com/download/win"
    }
}

# ─────────────────────────────────────────────────────────────────
#  STEP 3 — FFmpeg
# ─────────────────────────────────────────────────────────────────
function Step-FFmpeg {
    Step "Step 3 · Checking FFmpeg"
    try {
        $out = & ffmpeg -version 2>&1 | Select-Object -First 1 | Out-String
        Ok "FFmpeg detected — $($out.Trim())"
    } catch {
        Warn "FFmpeg not found. Some audio formats may not work."
        Info "Install: https://ffmpeg.org/download.html  or  winget install ffmpeg"
    }
}

# ─────────────────────────────────────────────────────────────────
#  STEP 4 — Change to project dir & Virtual Environment
# ─────────────────────────────────────────────────────────────────
function Step-Venv {
    Step "Step 4 · Setting up virtual environment"

    Set-Location $SCRIPT_DIR
    Info "Working directory: $SCRIPT_DIR"

    $venvPython = Join-Path $SCRIPT_DIR "$VENV_DIR\Scripts\python.exe"

    if (Test-Path $venvPython) {
        Skip "Virtual environment already exists at .\$VENV_DIR\"
    } else {
        Info "Creating virtual environment in .\$VENV_DIR ..."
        $result = & $script:PY -m venv $VENV_DIR 2>&1 | Out-String
        if (-not (Test-Path $venvPython)) {
            Fail "Failed to create virtual environment.`n$result" `
                 "Ensure the venv module is available and Python has write access to this folder."
        }
        Ok "Virtual environment created at .\$VENV_DIR"
    }

    $script:VENV_PY  = $venvPython
    $script:VENV_PIP = Join-Path $SCRIPT_DIR "$VENV_DIR\Scripts\pip.exe"
}

# ─────────────────────────────────────────────────────────────────
#  STEP 5 — Upgrade pip
# ─────────────────────────────────────────────────────────────────
function Step-PipUpgrade {
    Step "Step 5 · Upgrading pip"
    Info "Upgrading pip ..."
    & $script:VENV_PY -m pip install --upgrade pip --quiet 2>&1 | Out-Null
    Ok "pip upgraded"
}

# ─────────────────────────────────────────────────────────────────
#  STEP 6 — Install dependencies from requirements.txt
# ─────────────────────────────────────────────────────────────────
function Is-PkgInstalled([string]$pkg) {
    $out = & $script:VENV_PIP show $pkg 2>&1 | Out-String
    return $out -match "Name:"
}

function Step-Dependencies {
    Step "Step 6 · Installing Python dependencies"

    $reqFile = Join-Path $SCRIPT_DIR "requirements.txt"
    if (-not (Test-Path $reqFile)) {
        Fail "requirements.txt not found." `
             "Run install.ps1 from the IRIS AI project root directory."
    }

    $reqs = Get-Content $reqFile | Where-Object { $_.Trim() -ne "" -and -not $_.TrimStart().StartsWith("#") }

    foreach ($req in $reqs) {
        $req = $req.Trim()
        # Extract base package name
        $pkgName = ($req -split "[>=<!@\[]")[0].Trim()

        if (Is-PkgInstalled $pkgName) {
            Skip "$req — already installed"
            continue
        }

        Info "Installing $req ..."
        $out = & $script:VENV_PY -m pip install $req --quiet 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Fail "Failed to install: $req`n$out" `
                 "Try manually: $($script:VENV_PIP) install $req"
        }
        Ok "$req — installed"
    }
}

# ─────────────────────────────────────────────────────────────────
#  STEP 7 — Create directories
# ─────────────────────────────────────────────────────────────────
function Step-Directories {
    Step "Step 7 · Creating required directories"

    $dirs = @("voice", "logs", "cache", "temp", "config", ".iris")

    foreach ($d in $dirs) {
        $p = Join-Path $SCRIPT_DIR $d
        if (Test-Path $p) {
            Skip "$d/ — already exists"
        } else {
            New-Item -ItemType Directory -Path $p -Force | Out-Null
            Ok "$d/ — created"
        }
    }

    # voice/README.txt
    $voiceReadme = Join-Path $SCRIPT_DIR "voice\README.txt"
    if (-not (Test-Path $voiceReadme)) {
        @"
=== IRIS AI Voice Reference Directory ===

Place a reference voice audio file here (.wav, .mp3, or .flac).

IRIS AI automatically clones your voice for all spoken responses.
If no file is placed here, IRIS falls back to Edge TTS neural voice.
"@ | Set-Content -Path $voiceReadme -Encoding UTF8
        Ok "voice/README.txt — created"
    }
}

# ─────────────────────────────────────────────────────────────────
#  STEP 8 — First-run .env configuration
# ─────────────────────────────────────────────────────────────────
function Step-EnvConfig {
    Step "Step 8 · First-run configuration"

    $envPath     = Join-Path $SCRIPT_DIR ".env"
    $examplePath = Join-Path $SCRIPT_DIR ".env.example"

    if (Test-Path $envPath) {
        Skip ".env — already exists, preserving existing keys"
        return
    }

    $envContent = @"
# IRIS AI — Environment Configuration
# Get your free Groq API key at: https://console.groq.com

GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE

# Optional: Override the default Groq model
# GROQ_MODEL=llama-3.3-70b-versatile
"@

    if (Test-Path $examplePath) {
        Copy-Item $examplePath $envPath
        Ok ".env — copied from .env.example"
    } else {
        $envContent | Set-Content -Path $envPath -Encoding UTF8
        Ok ".env — created with template"
    }

    # Save example template
    if (-not (Test-Path $examplePath)) {
        $envContent | Set-Content -Path $examplePath -Encoding UTF8
    }

    Warn "ACTION REQUIRED: Open .env and set your GROQ_API_KEY"
    Info "Get a free key at: https://console.groq.com"
}

# ─────────────────────────────────────────────────────────────────
#  STEP 9 — Verify TTS dependencies
# ─────────────────────────────────────────────────────────────────
function Step-VerifyTTS {
    Step "Step 9 · Verifying TTS dependencies"

    $checks = @(
        @{ Code = "import edge_tts; print('ok')";   Name = "edge-tts (Neural TTS)" }
        @{ Code = "import pyttsx3; print('ok')";    Name = "pyttsx3 (SAPI5 fallback)" }
        @{ Code = "import sounddevice; print('ok')";Name = "sounddevice" }
        @{ Code = "import soundfile; print('ok')";  Name = "soundfile" }
    )

    foreach ($check in $checks) {
        $out = & $script:VENV_PY -c $check.Code 2>&1 | Out-String
        if ($out -match "ok") {
            Ok "$($check.Name) — ready"
        } else {
            Warn "$($check.Name) import check failed. TTS may fall back to system voice."
        }
    }
}

# ─────────────────────────────────────────────────────────────────
#  STEP 10 — Verify automation dependencies
# ─────────────────────────────────────────────────────────────────
function Step-VerifyAutomation {
    Step "Step 10 · Verifying automation dependencies"

    $checks = @(
        @{ Code = "import psutil; print('ok')";                     Name = "psutil" }
        @{ Code = "import pyautogui; print('ok')";                  Name = "pyautogui" }
        @{ Code = "import groq; print('ok')";                       Name = "groq (LLM engine)" }
        @{ Code = "from dotenv import load_dotenv; print('ok')";    Name = "python-dotenv" }
        @{ Code = "from rich.console import Console; print('ok')";  Name = "rich (UI engine)" }
        @{ Code = "import winreg; print('ok')";                     Name = "winreg (built-in)" }
    )

    foreach ($check in $checks) {
        $out = & $script:VENV_PY -c $check.Code 2>&1 | Out-String
        if ($out -match "ok") {
            Ok "$($check.Name) — ready"
        } else {
            Warn "$($check.Name) import check failed."
        }
    }
}

# ─────────────────────────────────────────────────────────────────
#  STEP 11 — Create launcher batch file
# ─────────────────────────────────────────────────────────────────
function Step-CreateLauncher {
    Step "Step 11 · Creating Windows launcher"

    $batPath = Join-Path $SCRIPT_DIR "iris_run.bat"

    if (Test-Path $batPath) {
        Skip "iris_run.bat — already exists"
        return
    }

    $batContent = @"
@echo off
REM IRIS AI Windows Launcher — auto-generated by install.ps1
title IRIS AI Terminal
cd /d "%~dp0"
if exist "$VENV_DIR\Scripts\python.exe" (
    "$VENV_DIR\Scripts\python.exe" iris.py %*
) else (
    python iris.py %*
)
pause
"@
    $batContent | Set-Content -Path $batPath -Encoding ASCII
    Ok "iris_run.bat — created (double-click to start IRIS)"
}

# ─────────────────────────────────────────────────────────────────
#  STEP 12 — Smoke test
# ─────────────────────────────────────────────────────────────────
function Step-SmokeTest {
    Step "Step 12 · Final smoke test"

    $smokeCode = @"
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, r'$($SCRIPT_DIR -replace "\\","\\\\")') 
import config, banner, ui
from commands import CommandProcessor
print('IRIS_MODULES_OK')
"@

    $out = & $script:VENV_PY -c $smokeCode 2>&1 | Out-String
    if ($out -match "IRIS_MODULES_OK") {
        Ok "All core IRIS modules imported successfully"
    } else {
        $errLines = ($out.Trim().Split("`n") | Select-Object -First 10) -join "`n    "
        Warn "Smoke test partial warning:`n    $errLines"
        Info "IRIS may still run fine. Try: python iris.py"
    }
}

# ─────────────────────────────────────────────────────────────────
#  STEP 13 — Write install log
# ─────────────────────────────────────────────────────────────────
function Step-WriteLog {
    Step "Step 13 · Writing installation log"
    LogWrite ""
    LogWrite "Installation completed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    LogWrite "Python executable : $($script:VENV_PY)"
    LogWrite "Working directory : $SCRIPT_DIR"
    LogWrite "Platform          : $([System.Environment]::OSVersion.VersionString)"
    FlushLog
    Ok "Install log saved → $LOG_FILE"
}

# ─────────────────────────────────────────────────────────────────
#  SUCCESS MESSAGE
# ─────────────────────────────────────────────────────────────────
function SuccessMessage {
    $line = "═" * 56
    Write-Host ""
    Write-Host "  ${GREEN}${BOLD}${line}${RESET}"
    Write-Host "  ${GREEN}${BOLD}  ✔  IRIS AI installed successfully.${RESET}"
    Write-Host "  ${GREEN}${BOLD}${line}${RESET}"
    Write-Host ""
    Write-Host "  ${CYAN}To start IRIS:${RESET}"
    Write-Host ""
    Write-Host "    ${BOLD}python iris.py${RESET}"
    Write-Host ""
    Write-Host "  ${DIM}Or double-click:  iris_run.bat${RESET}"
    Write-Host ""
    Write-Host "  ${DIM}Optional flags:${RESET}"
    Write-Host "  ${DIM}  python iris.py --theme jarvis${RESET}"
    Write-Host "  ${DIM}  python iris.py --no-boot${RESET}"
    Write-Host "  ${DIM}  python iris.py --debug${RESET}"
    Write-Host ""
    Write-Host "  ${YELLOW}⚠  Remember to set GROQ_API_KEY in .env before first run!${RESET}"
    Write-Host "  ${DIM}  Get a free key at: https://console.groq.com${RESET}"
    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────
Banner
LogWrite "IRIS AI PowerShell Installer started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
LogWrite "Working directory: $(Get-Location)"

Step-Python
Step-Git
Step-FFmpeg
Step-Venv
Step-PipUpgrade
Step-Dependencies
Step-Directories
Step-EnvConfig
Step-VerifyTTS
Step-VerifyAutomation
Step-CreateLauncher
Step-SmokeTest
Step-WriteLog
SuccessMessage
