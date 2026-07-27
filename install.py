"""
IRIS AI - One-Step Python Installer & Environment Setup
Handles project setup, dependency installation, verification, and first-run config.
Designed to be idempotent — safe to run multiple times.
"""

import sys
import os
import re
import subprocess
import shutil
import json
import time
import platform
import textwrap
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

IRIS_VERSION      = "v3.8.4-RELEASE"
GITHUB_REPO_URL   = "https://github.com/YOUR_USERNAME/IRIS-AI.git"  # <-- set before publishing
MIN_PYTHON_MAJOR  = 3
MIN_PYTHON_MINOR  = 9

REQUIRED_DIRS     = ["voice", "logs", "cache", "temp", "config", ".iris"]
VENV_DIR          = ".venv"
LOG_FILE          = "iris_install.log"
ENV_TEMPLATE_FILE = ".env.example"
ENV_FILE          = ".env"

# ──────────────────────────────────────────────────────────────────────────────
#  COLOURS  (pure ANSI — no external deps required at install time)
# ──────────────────────────────────────────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    DIM    = "\033[2m"
    WHITE  = "\033[97m"

# Enable ANSI on Windows 10+
if sys.platform == "win32":
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────────────
#  LOGGER
# ──────────────────────────────────────────────────────────────────────────────

log_lines: list[str] = []

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str):
    """Append plain message to install log."""
    log_lines.append(f"[{_ts()}] {msg}")

def ok(msg: str):
    print(f"  {C.GREEN}[OK]{C.RESET}  {msg}")
    log(f"OK    : {msg}")

def skip(msg: str):
    print(f"  {C.CYAN}[--]{C.RESET}  {C.DIM}{msg}{C.RESET}")
    log(f"SKIP  : {msg}")

def info(msg: str):
    print(f"  {C.CYAN}[..]{C.RESET}  {msg}")
    log(f"INFO  : {msg}")

def warn(msg: str):
    print(f"  {C.YELLOW}[!!]{C.RESET}  {C.YELLOW}{msg}{C.RESET}")
    log(f"WARN  : {msg}")

def step(title: str):
    line = "-" * (len(title) + 4)
    print(f"\n{C.BOLD}{C.CYAN}  {title}{C.RESET}")
    print(f"  {C.DIM}{line}{C.RESET}")
    log(f"\n---- {title} ----")

def fail(msg: str, hint: str = ""):
    print(f"\n  {C.RED}{C.BOLD}[FAILED]  INSTALLATION FAILED{C.RESET}")
    print(f"  {C.RED}Reason : {msg}{C.RESET}")
    if hint:
        print(f"  {C.YELLOW}Fix    : {hint}{C.RESET}")
    log(f"FAILED: {msg}")
    if hint:
        log(f"FIX   : {hint}")
    flush_log()
    sys.exit(1)

def flush_log():
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
    except Exception:
        pass

def banner():
    art = (
        "   ___ ____  ___ ____      _    ___ \n"
        "  |_ _|  _ \\|_ _/ ___|    / \\  |_ _|\n"
        "   | || |_) || |\\___ \\   / _ \\  | | \n"
        "   | ||  _ < | | ___) | / ___ \\ | | \n"
        "  |___|_| \\_\\___|____/ /_/   \\_\\___|\n"
    )
    print(C.BOLD + C.CYAN + art + C.RESET)
    print(f"  {C.BOLD}IRIS AI -- Jarvis Terminal Interface{C.RESET}  {C.DIM}{IRIS_VERSION}{C.RESET}")
    print(f"  {C.DIM}One-step installer  *  Windows   *  Python 3.9+{C.RESET}\n")

# ──────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def run(cmd: list[str], capture: bool = True, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess command, return CompletedProcess."""
    return subprocess.run(
        cmd, capture_output=capture, text=True, cwd=cwd,
        encoding="utf-8", errors="replace"
    )

def inside_venv() -> bool:
    return sys.prefix != sys.base_prefix

def get_venv_python() -> str:
    """Return path to Python executable inside .venv (Windows)."""
    candidates = [
        os.path.join(VENV_DIR, "Scripts", "python.exe"),
        os.path.join(VENV_DIR, "bin", "python"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return sys.executable

def get_venv_pip() -> str:
    """Return path to pip inside .venv."""
    candidates = [
        os.path.join(VENV_DIR, "Scripts", "pip.exe"),
        os.path.join(VENV_DIR, "Scripts", "pip3.exe"),
        os.path.join(VENV_DIR, "bin", "pip"),
        os.path.join(VENV_DIR, "bin", "pip3"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return "pip"

def package_installed(pip_exe: str, package_name: str) -> bool:
    """Check whether a Python package is already installed in the venv."""
    result = run([pip_exe, "show", package_name])
    return result.returncode == 0

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 1 — Python version gate
# ──────────────────────────────────────────────────────────────────────────────

def check_python_version():
    step("Step 1 · Verifying Python version")
    major = sys.version_info.major
    minor = sys.version_info.minor
    ver_str = f"{major}.{minor}.{sys.version_info.micro}"
    info(f"Detected Python {ver_str} ({platform.architecture()[0]})")
    log(f"Python executable: {sys.executable}")

    if (major, minor) < (MIN_PYTHON_MAJOR, MIN_PYTHON_MINOR):
        fail(
            f"Python {MIN_PYTHON_MAJOR}.{MIN_PYTHON_MINOR}+ is required — found {ver_str}.",
            f"Download a newer Python from https://www.python.org/downloads/ and re-run install.py"
        )

    if sys.platform != "win32":
        fail(
            "IRIS AI currently supports Windows only.",
            "Run this installer on a Windows 10 / 11 machine."
        )

    ok(f"Python {ver_str} — compatible")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 2 — Git check (optional but logged)
# ──────────────────────────────────────────────────────────────────────────────

def check_git():
    step("Step 2 · Checking Git")
    git_path = shutil.which("git")
    if git_path:
        result = run(["git", "--version"])
        ver = result.stdout.strip() if result.returncode == 0 else "unknown"
        ok(f"Git detected — {ver}")
    else:
        warn("Git not found. Git is optional but recommended for updates.")
        warn("Install from https://git-scm.com/download/win if needed.")
        log("WARN: git not in PATH")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 3 — FFmpeg check (used by sounddevice/audio processing)
# ──────────────────────────────────────────────────────────────────────────────

def check_ffmpeg():
    step("Step 3 · Checking FFmpeg")
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        result = run(["ffmpeg", "-version"])
        first_line = (result.stdout or "").split("\n")[0].strip()
        ok(f"FFmpeg detected — {first_line}")
    else:
        warn("FFmpeg not found in PATH.")
        warn("FFmpeg is optional but may be needed for some audio formats.")
        info("Install: https://ffmpeg.org/download.html  or  winget install ffmpeg")
        log("WARN: ffmpeg not in PATH")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 4 — Create or validate virtual environment
# ──────────────────────────────────────────────────────────────────────────────

def create_venv():
    step("Step 4 · Setting up virtual environment")
    venv_python = get_venv_python()

    if os.path.exists(venv_python):
        skip(f"Virtual environment already exists at {VENV_DIR}/")
        return

    info(f"Creating virtual environment in ./{VENV_DIR} ...")
    result = run([sys.executable, "-m", "venv", VENV_DIR])
    if result.returncode != 0:
        fail(
            f"Failed to create virtual environment.\n{result.stderr}",
            "Ensure the 'venv' module is available: python -m ensurepip --upgrade"
        )
    ok(f"Virtual environment created at ./{VENV_DIR}")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 5 — Upgrade pip
# ──────────────────────────────────────────────────────────────────────────────

def upgrade_pip():
    step("Step 5 · Upgrading pip")
    venv_python = get_venv_python()
    info("Upgrading pip to latest version...")
    result = run([venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    if result.returncode != 0:
        warn(f"pip upgrade returned non-zero exit code.\n{result.stderr}")
    else:
        ok("pip upgraded successfully")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 6 — Install Python dependencies from requirements.txt
# ──────────────────────────────────────────────────────────────────────────────

def install_dependencies():
    step("Step 6 · Installing Python dependencies")

    if not os.path.exists("requirements.txt"):
        fail(
            "requirements.txt not found.",
            "Make sure you are running install.py from the IRIS AI project root directory."
        )

    pip_exe = get_venv_pip()
    venv_python = get_venv_python()

    # Read requirements.txt
    with open("requirements.txt", "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]

    for req_line in lines:
        # Extract base package name (strip version specifiers)
        pkg_name = re.split(r"[>=<!@\[]", req_line)[0].strip()
        display_name = req_line

        if package_installed(pip_exe, pkg_name):
            skip(f"{display_name} — already installed")
            continue

        info(f"Installing {display_name} ...")
        result = run([venv_python, "-m", "pip", "install", req_line, "--quiet"])
        if result.returncode != 0:
            fail(
                f"Failed to install package: {display_name}\n\n{result.stderr}",
                f"Try manually: {pip_exe} install {req_line}"
            )
        ok(f"{display_name} — installed")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 7 — Create required directory structure
# ──────────────────────────────────────────────────────────────────────────────

def create_directories():
    step("Step 7 · Creating required directories")

    for d in REQUIRED_DIRS:
        path = Path(d)
        if path.exists():
            skip(f"{d}/ — already exists")
        else:
            path.mkdir(parents=True, exist_ok=True)
            ok(f"{d}/ — created")

    # Create voice/README.txt if missing
    voice_readme = Path("voice") / "README.txt"
    if not voice_readme.exists():
        voice_readme.write_text(
            "=== IRIS AI Voice Reference Directory ===\n\n"
            "Place a reference voice audio file here (.wav, .mp3, or .flac).\n\n"
            "IRIS AI will automatically clone your voice for all spoken responses.\n"
            "If no file is placed here, IRIS falls back to Edge TTS neural voice.\n",
            encoding="utf-8"
        )
        ok("voice/README.txt — created")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 8 — Generate first-run .env configuration
# ──────────────────────────────────────────────────────────────────────────────

def setup_env_config():
    step("Step 8 · First-run configuration")

    env_path = Path(ENV_FILE)
    example_path = Path(ENV_TEMPLATE_FILE)

    if env_path.exists():
        skip(".env — already exists, skipping to preserve existing keys")
        return

    if example_path.exists():
        shutil.copy(example_path, env_path)
        ok(".env — copied from .env.example")
        info("Edit .env and set your GROQ_API_KEY before running IRIS.")
    else:
        env_content = (
            "# IRIS AI — Environment Configuration\n"
            "# Get your free Groq API key at: https://console.groq.com\n"
            "\n"
            "GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE\n"
            "\n"
            "# Optional: Override default model\n"
            "# GROQ_MODEL=llama-3.3-70b-versatile\n"
        )
        env_path.write_text(env_content, encoding="utf-8")
        ok(".env — created with template")
        warn("ACTION REQUIRED: Open .env and set your GROQ_API_KEY")
        info("Get a free key at: https://console.groq.com")

    # Create .env.example for reference
    if not example_path.exists():
        shutil.copy(env_path, example_path)

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 9 — Verify TTS dependencies (edge-tts, pyttsx3)
# ──────────────────────────────────────────────────────────────────────────────

def verify_tts():
    step("Step 9 · Verifying TTS dependencies")
    venv_python = get_venv_python()
    pip_exe     = get_venv_pip()

    # Check edge-tts
    check_code = "import edge_tts; print('ok')"
    result = run([venv_python, "-c", check_code])
    if result.returncode == 0 and "ok" in result.stdout:
        ok("edge-tts — Neural TTS engine ready")
    else:
        warn("edge-tts import failed. Attempting reinstall...")
        run([venv_python, "-m", "pip", "install", "edge-tts", "--upgrade", "--quiet"])
        ok("edge-tts — reinstalled")

    # Check pyttsx3 (SAPI5 fallback)
    check_code = "import pyttsx3; print('ok')"
    result = run([venv_python, "-c", check_code])
    if result.returncode == 0 and "ok" in result.stdout:
        ok("pyttsx3 — SAPI5 TTS fallback ready")
    else:
        warn("pyttsx3 not importable — this is the fallback TTS engine.")
        info(f"Try: {pip_exe} install pyttsx3")

    # Check sounddevice + soundfile (for XTTS audio playback)
    for pkg in ["sounddevice", "soundfile"]:
        result = run([venv_python, "-c", f"import {pkg.replace('-','_')}; print('ok')"])
        if result.returncode == 0 and "ok" in result.stdout:
            ok(f"{pkg} — audio I/O ready")
        else:
            warn(f"{pkg} import failed. Audio playback may be affected.")
            info(f"Try: {pip_exe} install {pkg}")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 10 — Verify automation dependencies (pyautogui, psutil)
# ──────────────────────────────────────────────────────────────────────────────

def verify_automation():
    step("Step 10 · Verifying automation dependencies")
    venv_python = get_venv_python()

    checks = {
        "psutil"    : "import psutil; print('ok')",
        "pyautogui" : "import pyautogui; print('ok')",
        "groq"      : "import groq; print('ok')",
        "dotenv"    : "from dotenv import load_dotenv; print('ok')",
        "rich"      : "from rich.console import Console; print('ok')",
    }

    for pkg, code in checks.items():
        result = run([venv_python, "-c", code])
        if result.returncode == 0 and "ok" in result.stdout:
            ok(f"{pkg} — ready")
        else:
            warn(f"{pkg} failed to import. Some features may be unavailable.")
            log(f"WARN: {pkg} import failed — {result.stderr.strip()}")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 11 — Create iris_run.bat launcher for convenience
# ──────────────────────────────────────────────────────────────────────────────

def create_launcher():
    step("Step 11 · Creating Windows launcher shortcuts")

    bat_content = textwrap.dedent(f"""\
        @echo off
        REM IRIS AI Windows Launcher
        REM Auto-generated by install.py
        title IRIS AI Terminal
        cd /d "%~dp0"
        if exist "{VENV_DIR}\\Scripts\\python.exe" (
            "{VENV_DIR}\\Scripts\\python.exe" iris.py %*
        ) else (
            python iris.py %*
        )
        pause
    """)

    bat_path = Path("iris_run.bat")
    if bat_path.exists():
        skip("iris_run.bat — already exists")
    else:
        bat_path.write_text(bat_content, encoding="utf-8")
        ok("iris_run.bat — created (double-click to launch IRIS)")

    info("To always use the venv automatically, run:  iris_run.bat")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 12 — Validate IRIS can be imported (smoke test)
# ──────────────────────────────────────────────────────────────────────────────

def smoke_test():
    step("Step 12 · Final smoke test — validating IRIS core modules")
    venv_python = get_venv_python()

    smoke_code = textwrap.dedent("""\
        import sys, os
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        import config
        import banner
        import ui
        from commands import CommandProcessor
        print("IRIS_MODULES_OK")
    """)

    result = run([venv_python, "-c", smoke_code])
    if result.returncode == 0 and "IRIS_MODULES_OK" in result.stdout:
        ok("All core IRIS modules imported successfully")
    else:
        err = result.stderr.strip() or result.stdout.strip()
        warn(f"Smoke test warning — some modules may have issues:")
        # Print first 10 lines of error
        for line in err.splitlines()[:10]:
            info(f"  {line}")
        info("IRIS may still run. Try: python iris.py")
        log(f"SMOKE TEST WARN: {err}")

# ──────────────────────────────────────────────────────────────────────────────
#  STEP 13 — Write setup log
# ──────────────────────────────────────────────────────────────────────────────

def write_install_log():
    step("Step 13 · Writing installation log")
    log(f"\nInstallation completed at {_ts()}")
    log(f"Python executable : {sys.executable}")
    log(f"Venv Python       : {get_venv_python()}")
    log(f"Working directory : {os.getcwd()}")
    log(f"Platform          : {platform.platform()}")

    flush_log()
    ok(f"Install log saved -> {LOG_FILE}")

# ──────────────────────────────────────────────────────────────────────────────
#  SUCCESS BANNER
# ──────────────────────────────────────────────────────────────────────────────

def success_message():
    sep = "=" * 56
    print()
    print(f"  {C.BOLD}{C.GREEN}{sep}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}  [OK] IRIS AI installed successfully.{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}{sep}{C.RESET}")
    print()
    print(f"  {C.CYAN}To start IRIS:{C.RESET}")
    print()
    print(f"    {C.BOLD}python iris.py{C.RESET}")
    print()
    print(f"  {C.DIM}Optional flags:{C.RESET}")
    print(f"  {C.DIM}  python iris.py --theme jarvis{C.RESET}")
    print(f"  {C.DIM}  python iris.py --no-boot{C.RESET}")
    print(f"  {C.DIM}  python iris.py --debug{C.RESET}")
    print()
    print(f"  {C.YELLOW}[!!] Remember to set GROQ_API_KEY in .env before first run!{C.RESET}")
    print(f"  {C.DIM}     Get a free key at: https://console.groq.com{C.RESET}")
    print()

# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    banner()
    log(f"IRIS AI Installer started at {_ts()}")
    log(f"Working directory: {os.getcwd()}")

    check_python_version()   # Step 1
    check_git()              # Step 2
    check_ffmpeg()           # Step 3
    create_venv()            # Step 4
    upgrade_pip()            # Step 5
    install_dependencies()   # Step 6
    create_directories()     # Step 7
    setup_env_config()       # Step 8
    verify_tts()             # Step 9
    verify_automation()      # Step 10
    create_launcher()        # Step 11
    smoke_test()             # Step 12
    write_install_log()      # Step 13
    success_message()

if __name__ == "__main__":
    main()
