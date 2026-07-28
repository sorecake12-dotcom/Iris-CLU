"""
IRIS AI - Secure Multi-Provider API Key Manager
Manages Groq (Normal Mode) and Gemini (Coding Mode) API keys.
Keys are stored locally in config/config.json — NEVER hardcoded or committed to Git.
"""

import os
import sys
import json
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.table import Table
from rich import box

console = Console()

# ─────────────────────────────────────────────────────────────────
#  Storage  (excluded from Git via .gitignore)
# ─────────────────────────────────────────────────────────────────
CONFIG_DIR  = Path(__file__).parent / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Environment variable names
GROQ_KEY_ENV   = "GROQ_API_KEY"
GEMINI_KEY_ENV = "GEMINI_API_KEY"


# ─────────────────────────────────────────────────────────────────
#  Config file I/O
# ─────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    """Load config.json from disk. Returns empty dict if missing or corrupt."""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_config(data: dict):
    """Persist config dict to config/config.json (mode 0o600 — owner-only read)."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            CONFIG_FILE.chmod(0o600)  # restrict to owner on Unix; no-op on Windows
        except Exception:
            pass
    except Exception as ex:
        console.print(f"[bold red][CONFIG] Failed to save config: {ex}[/bold red]")

def _mask(key: str) -> str:
    """Return a masked representation of a key for safe display (never print raw keys)."""
    if not key or len(key) < 8:
        return "[not set]"
    return f"{key[:6]}{'*' * (len(key) - 10)}{key[-4:]}"


# ─────────────────────────────────────────────────────────────────
#  Groq Key — get / save / validate
# ─────────────────────────────────────────────────────────────────

def get_groq_api_key() -> str:
    """
    Resolve Groq API key in priority order:
      1. GROQ_API_KEY environment variable
      2. config/config.json
    Returns empty string if not found.
    """
    env_key = os.environ.get(GROQ_KEY_ENV, "").strip()
    if env_key and not env_key.startswith("YOUR_"):
        return env_key

    cfg = _load_config()
    stored = cfg.get("groq_api_key", "").strip()
    if stored and not stored.startswith("YOUR_"):
        os.environ[GROQ_KEY_ENV] = stored
        return stored

    return ""

def save_groq_api_key(key: str):
    """Persist Groq API key to config/config.json and inject into environment."""
    key = key.strip()
    cfg = _load_config()
    cfg["groq_api_key"] = key
    _save_config(cfg)
    os.environ[GROQ_KEY_ENV] = key

def delete_groq_api_key():
    """Remove Groq API key from config and environment."""
    cfg = _load_config()
    cfg.pop("groq_api_key", None)
    _save_config(cfg)
    os.environ.pop(GROQ_KEY_ENV, None)

def validate_groq_key(key: str) -> tuple[bool, str]:
    """
    Live validation: make a minimal test call to Groq API.
    Returns (True, "OK") or (False, error_reason).
    """
    key = key.strip()
    if not key:
        return False, "API key is empty."
    if not key.startswith("gsk_"):
        return False, "Groq API keys always start with 'gsk_'. The key you entered doesn't look right."

    try:
        from groq import Groq
        client = Groq(api_key=key)
        client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
            stream=False
        )
        return True, "OK"
    except Exception as ex:
        s = str(ex).lower()
        if "401" in s or "invalid api key" in s or "authentication" in s:
            return False, "Invalid API key. Double-check it at https://console.groq.com"
        if "429" in s or "rate" in s:
            return True, "OK (rate-limited, key accepted)"
        if "connection" in s or "network" in s or "timeout" in s:
            return False, "Cannot reach Groq servers. Check your internet connection."
        return False, f"Unexpected error: {ex}"


# ─────────────────────────────────────────────────────────────────
#  Gemini Key — get / save / validate
# ─────────────────────────────────────────────────────────────────

def get_gemini_api_key() -> str:
    """
    Resolve Gemini API key in priority order:
      1. GEMINI_API_KEY environment variable
      2. config/config.json
    Returns empty string if not found.
    """
    env_key = os.environ.get(GEMINI_KEY_ENV, "").strip()
    if env_key and not env_key.startswith("YOUR_"):
        return env_key

    cfg = _load_config()
    stored = cfg.get("gemini_api_key", "").strip()
    if stored and not stored.startswith("YOUR_"):
        os.environ[GEMINI_KEY_ENV] = stored
        return stored

    return ""

def save_gemini_api_key(key: str):
    """Persist Gemini API key to config/config.json and inject into environment."""
    key = key.strip()
    cfg = _load_config()
    cfg["gemini_api_key"] = key
    _save_config(cfg)
    os.environ[GEMINI_KEY_ENV] = key

def delete_gemini_api_key():
    """Remove Gemini API key from config and environment."""
    cfg = _load_config()
    cfg.pop("gemini_api_key", None)
    _save_config(cfg)
    os.environ.pop(GEMINI_KEY_ENV, None)

def validate_gemini_key(key: str) -> tuple[bool, str]:
    """
    Live validation: make a minimal test call to Google Gemini API.
    Returns (True, "OK") or (False, error_reason).
    """
    key = key.strip()
    if not key:
        return False, "API key is empty."
    if not key.startswith("AIza"):
        return False, "Gemini API keys always start with 'AIza'. The key you entered doesn't look right."

    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        model.generate_content("Hi", generation_config={"max_output_tokens": 1})
        return True, "OK"
    except ImportError:
        # google-generativeai not installed — do format-only validation
        return True, "OK (google-generativeai not installed; format accepted)"
    except Exception as ex:
        s = str(ex).lower()
        if "api key" in s or "invalid" in s or "401" in s or "403" in s or "permission" in s:
            return False, "Invalid API key. Get yours at https://aistudio.google.com/app/apikey"
        if "429" in s or "quota" in s or "rate" in s:
            return True, "OK (rate-limited, key accepted)"
        if "connection" in s or "network" in s or "timeout" in s:
            return False, "Cannot reach Google servers. Check your internet connection."
        return False, f"Unexpected error: {ex}"


# ─────────────────────────────────────────────────────────────────
#  API Status
# ─────────────────────────────────────────────────────────────────

def get_api_status() -> dict:
    """Return a summary of the current API key configuration (no raw keys)."""
    groq_key   = get_groq_api_key()
    gemini_key = get_gemini_api_key()
    return {
        "groq": {
            "configured": bool(groq_key),
            "masked":     _mask(groq_key) if groq_key else "[not configured]",
            "mode":       "Normal Mode / Voice / Automation",
        },
        "gemini": {
            "configured": bool(gemini_key),
            "masked":     _mask(gemini_key) if gemini_key else "[not configured]",
            "mode":       "Coding Mode only",
        },
    }


# ─────────────────────────────────────────────────────────────────
#  Interactive key collection helpers
# ─────────────────────────────────────────────────────────────────

def _collect_groq_key(required: bool = True) -> str:
    """
    Prompt user for Groq key with validation loop.
    If required=False, allows skipping by pressing Enter.
    Returns the validated key, or "" if skipped.
    """
    attempts = 0
    while True:
        attempts += 1
        console.print()
        try:
            raw = Prompt.ask(
                "[bold bright_cyan]  Groq API Key[/bold bright_cyan]"
                + ("" if required else " [dim](press Enter to skip)[/dim]"),
                password=False
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim yellow]  Setup cancelled.[/dim yellow]\n")
            sys.exit(0)

        if not raw:
            if not required:
                return ""
            console.print("[yellow]  [!!] Groq key is required — IRIS cannot run without it.[/yellow]")
            continue

        if not raw.startswith("gsk_"):
            console.print(
                "[red]  [!!] That doesn't look like a Groq key (should start with 'gsk_').\n"
                "       Get yours at: https://console.groq.com[/red]"
            )
            continue

        console.print("[dim cyan]  [..] Validating Groq key...[/dim cyan]")
        valid, msg = validate_groq_key(raw)
        if valid:
            console.print("[green]  [OK] Groq key accepted.[/green]")
            return raw
        else:
            console.print(f"[bold red]  [!!] Groq validation failed:[/bold red] [red]{msg}[/red]")
            if attempts >= 3:
                console.print("[dim yellow]  Tip: Copy the full key from https://console.groq.com -> API Keys[/dim yellow]")


def _collect_gemini_key(required: bool = False) -> str:
    """
    Prompt user for Gemini key with validation loop.
    Always skippable — Coding Mode is optional.
    Returns the validated key, or "" if skipped.
    """
    attempts = 0
    while True:
        attempts += 1
        console.print()
        try:
            raw = Prompt.ask(
                "[bold bright_magenta]  Gemini API Key[/bold bright_magenta]"
                " [dim](press Enter to skip — enables Coding Mode later)[/dim]",
                password=False
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim yellow]  Setup cancelled.[/dim yellow]\n")
            sys.exit(0)

        if not raw:
            console.print("[dim yellow]  [--] Gemini key skipped. Coding Mode will be disabled.[/dim yellow]")
            return ""

        if not raw.startswith("AIza"):
            console.print(
                "[red]  [!!] That doesn't look like a Gemini key (should start with 'AIza').\n"
                "       Get yours at: https://aistudio.google.com/app/apikey[/red]"
            )
            continue

        console.print("[dim cyan]  [..] Validating Gemini key...[/dim cyan]")
        valid, msg = validate_gemini_key(raw)
        if valid:
            console.print("[green]  [OK] Gemini key accepted.[/green]")
            return raw
        else:
            console.print(f"[bold red]  [!!] Gemini validation failed:[/bold red] [red]{msg}[/red]")
            console.print("[dim yellow]  [--] Skipping Gemini for now. You can add it later with: configure api[/dim yellow]")
            return ""


# ─────────────────────────────────────────────────────────────────
#  Full setup wizard  (first-run or /configureapi command)
# ─────────────────────────────────────────────────────────────────

def run_setup_wizard(update_groq: bool = True, update_gemini: bool = True) -> None:
    """
    Interactive setup wizard for one or both API keys.
    Shows a branded panel, collects & validates keys, saves them locally.
    """
    console.clear()

    # Title panel
    intro = Text()
    intro.append("\n  Welcome to IRIS AI Setup\n\n", style="bold bright_cyan")
    intro.append(
        "  IRIS uses two independent AI providers:\n\n",
        style="dim white"
    )
    intro.append(
        "  [1] Groq API Key     — required for all core features\n"
        "      (chat, voice, automation, timers, general knowledge)\n\n",
        style="cyan"
    )
    intro.append(
        "  [2] Gemini API Key   — optional, enables Coding Mode only\n"
        "      (code generation, bug fixing, file editing, refactoring)\n\n",
        style="bright_magenta"
    )
    intro.append(
        "  Keys are stored in  config/config.json  on this computer only.\n"
        "  They are NEVER uploaded to GitHub or printed to the terminal.\n",
        style="dim green"
    )

    console.print(Panel(
        intro,
        title="[bold bright_cyan]  IRIS AI  --  API Configuration  [/bold bright_cyan]",
        border_style="bright_cyan",
        padding=(0, 2)
    ))

    # --- Collect Groq ---
    if update_groq:
        console.print("\n[bold cyan]  -- Groq API Key (console.groq.com) --[/bold cyan]")
        groq_key = _collect_groq_key(required=True)
        save_groq_api_key(groq_key)

    # --- Collect Gemini ---
    if update_gemini:
        console.print("\n[bold magenta]  -- Gemini API Key (aistudio.google.com) --[/bold magenta]")
        gemini_key = _collect_gemini_key(required=False)
        if gemini_key:
            save_gemini_api_key(gemini_key)

    # Confirmation
    console.print()
    console.print(Panel(
        "[bold bright_green]  Configuration saved![/bold bright_green]\n\n"
        "  Groq key  : stored in config/config.json\n"
        "  Gemini key: stored in config/config.json\n\n"
        "  [dim]Run  configure api  at any time to update your keys.[/dim]\n\n"
        "  [bold white]Launching IRIS AI...[/bold white]",
        border_style="bright_green",
        padding=(0, 2)
    ))
    time.sleep(1.5)


# ─────────────────────────────────────────────────────────────────
#  Entry-point check  (called from iris.py startup)
# ─────────────────────────────────────────────────────────────────

def ensure_api_keys_configured() -> None:
    """
    Called at IRIS startup. If Groq key is present, returns silently.
    If missing, runs the full first-run setup wizard.
    Gemini is always optional — never blocks startup.
    """
    if get_groq_api_key():
        return
    # No Groq key — wizard is mandatory
    run_setup_wizard(update_groq=True, update_gemini=True)


# Keep backwards-compatible alias used in iris.py
ensure_api_key_configured = ensure_api_keys_configured


# ─────────────────────────────────────────────────────────────────
#  Runtime helpers for commands
# ─────────────────────────────────────────────────────────────────

def print_api_status(theme_key: str = "emerald"):
    """Print a Rich table showing API key status (masked — no raw keys)."""
    import config as cfg_module
    t = cfg_module.THEMES.get(theme_key, cfg_module.THEMES[cfg_module.DEFAULT_THEME])
    status = get_api_status()

    table = Table(
        title="[bold cyan][::] API CONFIGURATION STATUS [::][/bold cyan]",
        border_style=t["border"],
        box=box.ROUNDED
    )
    table.add_column("Provider",    style=f"bold {t['accent']}", no_wrap=True)
    table.add_column("Status",      style="white",  no_wrap=True)
    table.add_column("Key (masked)", style="dim white")
    table.add_column("Used For",    style="dim cyan")

    groq = status["groq"]
    gemini = status["gemini"]

    groq_status = "[bold green][OK] Configured[/bold green]" if groq["configured"] else "[bold red][!!] Missing[/bold red]"
    gem_status  = "[bold green][OK] Configured[/bold green]" if gemini["configured"] else "[bold yellow][--] Not set[/bold yellow]"

    table.add_row("Groq",   groq_status,   groq["masked"],   groq["mode"])
    table.add_row("Gemini", gem_status,    gemini["masked"], gemini["mode"])

    console.print()
    console.print(table)
    console.print()
    if not gemini["configured"]:
        console.print(
            "[dim yellow]  Tip: Coding Mode requires a Gemini key. "
            "Run  [bold white]configure api[/bold white]  or  [bold white]update gemini api[/bold white]  to add it.[/dim yellow]\n"
        )


def reset_api_config():
    """Delete all stored API keys from config.json and environment."""
    cfg = _load_config()
    cfg.pop("groq_api_key", None)
    cfg.pop("gemini_api_key", None)
    _save_config(cfg)
    os.environ.pop(GROQ_KEY_ENV, None)
    os.environ.pop(GEMINI_KEY_ENV, None)
    console.print("[bold yellow]  [!!] All API keys have been cleared from config/config.json.[/bold yellow]")
    console.print("[dim]  Run  python iris.py  to re-enter your keys.[/dim]\n")


def check_gemini_available() -> tuple[bool, str]:
    """
    Returns (True, "") if a Gemini key is configured.
    Returns (False, user_message) if Coding Mode cannot start.
    """
    key = get_gemini_api_key()
    if key:
        return True, ""
    return False, (
        "Gemini API key is not configured. Coding Mode requires a Gemini API key.\n"
        "  Run  [bold white]configure api[/bold white]  or  [bold white]update gemini api[/bold white]  to add your key.\n"
        "  Get a free key at: https://aistudio.google.com/app/apikey"
    )
