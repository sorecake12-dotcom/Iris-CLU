"""
IRIS AI - Secure API Key Manager
Handles first-run setup wizard, local key storage in config/config.json,
and key validation. Keys are NEVER hardcoded or committed to Git.
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

console = Console()

# Storage location — excluded from Git via .gitignore
CONFIG_DIR  = Path(__file__).parent / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Environment variable name
GROQ_KEY_ENV = "GROQ_API_KEY"


# ─────────────────────────────────────────────────────────────────
#  Config file I/O
# ─────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    """Load config.json from disk. Returns empty dict if missing."""
    try:
        if CONFIG_FILE.exists():
            raw = CONFIG_FILE.read_text(encoding="utf-8")
            return json.loads(raw)
    except Exception:
        pass
    return {}

def _save_config(data: dict):
    """Persist config dict to config/config.json."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )
    except Exception as ex:
        console.print(f"[bold red][CONFIG] Failed to save config: {ex}[/bold red]")


# ─────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────

def get_groq_api_key() -> str:
    """
    Resolve Groq API key in priority order:
      1. GROQ_API_KEY environment variable (set by system or user shell)
      2. config/config.json  (saved by first-run wizard)
    Returns empty string if not found anywhere.
    """
    # 1 — environment variable
    env_key = os.environ.get(GROQ_KEY_ENV, "").strip()
    if env_key and not env_key.startswith("YOUR_"):
        return env_key

    # 2 — local config file
    cfg = _load_config()
    stored = cfg.get("groq_api_key", "").strip()
    if stored and not stored.startswith("YOUR_"):
        # Inject into environment so child imports can use os.environ too
        os.environ[GROQ_KEY_ENV] = stored
        return stored

    return ""


def save_groq_api_key(key: str):
    """Save the Groq API key to config/config.json and inject it into env."""
    key = key.strip()
    cfg = _load_config()
    cfg["groq_api_key"] = key
    _save_config(cfg)
    os.environ[GROQ_KEY_ENV] = key


def validate_groq_key(key: str) -> tuple[bool, str]:
    """
    Make a lightweight test call to the Groq API to verify the key is valid.
    Returns (True, "OK") on success or (False, error_message) on failure.
    """
    key = key.strip()
    if not key:
        return False, "API key is empty."
    if not key.startswith("gsk_"):
        return False, "Groq API keys start with 'gsk_'. The key you entered doesn't look right."

    try:
        from groq import Groq, AuthenticationError, BadRequestError
        client = Groq(api_key=key)
        # Minimal token request — cheapest possible validation call
        client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
            stream=False
        )
        return True, "OK"
    except Exception as ex:
        ex_str = str(ex).lower()
        if "401" in ex_str or "invalid api key" in ex_str or "authentication" in ex_str:
            return False, "Invalid API key. Please double-check the key and try again."
        if "429" in ex_str or "rate" in ex_str:
            # Rate-limited but key is real — treat as valid
            return True, "OK (rate-limited, but key is accepted)"
        if "connection" in ex_str or "network" in ex_str or "timeout" in ex_str:
            return False, "Could not reach Groq servers. Check your internet connection."
        return False, f"Unexpected error: {ex}"


# ─────────────────────────────────────────────────────────────────
#  First-run setup wizard
# ─────────────────────────────────────────────────────────────────

def run_setup_wizard() -> str:
    """
    Interactive first-run wizard that collects and validates the Groq API key.
    Loops until a valid key is provided or the user quits.
    Returns the validated API key.
    """
    console.clear()

    # Header panel
    header = Text()
    header.append("\n  Welcome to IRIS AI!\n", style="bold bright_cyan")
    header.append(
        "\n  Before we begin, you need a free Groq API key so IRIS can think.\n"
        "  It takes about 30 seconds to get one.\n",
        style="dim white"
    )
    header.append(
        "\n  Steps:\n"
        "  1. Open  https://console.groq.com  in your browser\n"
        "  2. Sign up (free — no credit card required)\n"
        "  3. Go to  API Keys  ->  Create API Key\n"
        "  4. Copy the key and paste it below\n",
        style="cyan"
    )
    header.append(
        "\n  Your key will be stored locally on this computer only.\n"
        "  It will NEVER be uploaded to GitHub or shared anywhere.\n",
        style="dim green"
    )

    console.print(Panel(
        header,
        title="[bold bright_cyan]  IRIS AI  —  First-Run Setup  [/bold bright_cyan]",
        border_style="bright_cyan",
        padding=(0, 2)
    ))

    attempts = 0
    while True:
        attempts += 1
        console.print()

        try:
            raw_key = Prompt.ask(
                "[bold bright_cyan]  Paste your Groq API Key[/bold bright_cyan]",
                password=False
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim yellow]  Setup cancelled. Run 'python iris.py' again to complete setup.[/dim yellow]\n")
            sys.exit(0)

        if not raw_key:
            console.print("[yellow]  [!!] No key entered. Please paste your Groq API key.[/yellow]")
            continue

        # Quick format check before making a network call
        if not raw_key.startswith("gsk_"):
            console.print(
                "[red]  [!!] That doesn't look like a Groq key — they always start with 'gsk_'.\n"
                "       Please copy the key from https://console.groq.com and try again.[/red]"
            )
            continue

        # Validate against the API
        console.print("[dim cyan]  [..] Validating key with Groq...[/dim cyan]")
        valid, message = validate_groq_key(raw_key)

        if valid:
            save_groq_api_key(raw_key)
            console.print()
            console.print(Panel(
                "[bold bright_green]  [OK] API key accepted and saved!  [/bold bright_green]\n\n"
                "  Your key is stored in  config/config.json\n"
                "  This file is excluded from Git and will never be shared.\n\n"
                "  [bold white]Launching IRIS AI...[/bold white]",
                border_style="bright_green",
                padding=(0, 2)
            ))
            time.sleep(1.5)
            return raw_key
        else:
            console.print(f"\n[bold red]  [!!] Key validation failed:[/bold red] [red]{message}[/red]")
            if attempts >= 3:
                console.print(
                    "[dim yellow]\n  Tip: Make sure you copied the entire key from\n"
                    "  https://console.groq.com -> API Keys -> your key\n[/dim yellow]"
                )


# ─────────────────────────────────────────────────────────────────
#  Entry-point check — called once at IRIS startup
# ─────────────────────────────────────────────────────────────────

def ensure_api_key_configured() -> str:
    """
    Called at IRIS startup. If a valid key already exists, returns it silently.
    If no key is found, runs the interactive first-run setup wizard.
    Returns the API key string.
    """
    key = get_groq_api_key()
    if key:
        return key
    # No key found — run the wizard
    return run_setup_wizard()
