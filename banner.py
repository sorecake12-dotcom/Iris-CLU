"""
IRIS AI - Proportional Premium Developer CLI Banner & Status HUD Matrix
Inspired by Claude Code, Warp Terminal, and cinematic JARVIS consoles.
"""

import sys
import os
import time
import shutil
import platform
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich import box

import config

if sys.platform == "win32":
    os.system("")

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

console = Console()
SESSION_START_TIME = time.time()

# Native ANSI Neon Green
NEON_GREEN = "\033[1;38;2;0;255;102m"
RESET = "\033[0m"

# User Provided IRIS AI Block Banner
IRIS_BLOCK_BANNER = [
    r"██╗██████╗ ██╗███████╗         █████╗ ██╗",
    r"██║██╔══██╗██║██╔════╝        ██╔══██╗██║",
    r"██║██████╔╝██║███████╗        ███████║██║",
    r"██║██╔══██╗██║╚════██║        ██╔══██║██║",
    r"██║██║  ██║██║███████║██╗     ██║  ██║██║",
    r"╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝"
]

TAGLINE = "❖ IRIS AI CORE INTERFACE ❖"


def get_session_uptime() -> str:
    """Format session uptime HH:MM:SS."""
    elapsed = int(time.time() - SESSION_START_TIME)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def render_scifi_status_hud(state="IDLE", theme_key="emerald"):
    """
    Renders a proportional, balanced Sci-Fi Status HUD matrix.
    Width matches the banner (~70 chars wide) and eliminates text truncation.
    """
    from llm_engine import llm_engine
    from voice_engine import voice_engine

    t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])
    accent = t["accent"]
    border_col = t["border"]

    # Telemetry Data
    core_status = "🟢 ONLINE"
    groq_status = "🟢 CONNECTED" if llm_engine.client else "🔴 DISCONNECTED"
    active_model = llm_engine.model_name

    # Voice Engine & Active Voice
    if voice_engine.cloning_active and voice_engine.current_voice_file:
        voice_mode = "XTTS v2 (Cloned)"
        active_voice = os.path.basename(voice_engine.current_voice_file)
    else:
        try:
            import edge_tts
            voice_mode = "Edge Neural TTS"
            active_voice = "en-US-Christopher"
        except ImportError:
            voice_mode = "System SAPI5"
            active_voice = "Standard TTS"

    # Speech State Indicator
    if state == "SPEAKING" or voice_engine.is_playing:
        speech_status = "🔊 SPEAKING"
    elif state == "THINKING":
        speech_status = "🟡 THINKING"
    elif state == "LISTENING":
        speech_status = "🟡 LISTENING"
    else:
        speech_status = "🟢 IDLE"

    mic_status = "🟢 READY"
    uptime = get_session_uptime()
    now_str = datetime.now().strftime("%H:%M:%S")

    # Balanced 2-Column Table Grid (Width ~68 chars)
    hud_table = Table(box=box.ROUNDED, border_style=border_col, padding=(0, 1), show_header=False, expand=True)

    hud_table.add_column("Col1", justify="left", ratio=1)
    hud_table.add_column("Col2", justify="left", ratio=1)

    hud_table.add_row(
        f"[bold white]Neural Core:[/bold white] {core_status}",
        f"[bold white]Voice Engine:[/bold white] [cyan]{voice_mode}[/cyan]"
    )
    hud_table.add_row(
        f"[bold white]Groq API:[/bold white] {groq_status}",
        f"[bold white]Active Voice:[/bold white] [bold cyan]{active_voice}[/bold cyan]"
    )
    hud_table.add_row(
        f"[bold white]Active Model:[/bold white] [bold bright_green]{active_model}[/bold bright_green]",
        f"[bold white]Speech Status:[/bold white] {speech_status}"
    )
    hud_table.add_row(
        f"[bold white]Microphone:[/bold white] {mic_status}",
        f"[bold white]Current Time:[/bold white] [cyan]{now_str}[/cyan]"
    )
    hud_table.add_row(
        f"[bold white]Session Uptime:[/bold white] [dim]{uptime}[/dim]",
        f"[bold white]Interface Mode:[/bold white] [cyan]Cyberpunk HUD[/cyan]"
    )

    # Wrap in fixed-width panel matching banner proportion (~72 chars wide)
    term_width = shutil.get_terminal_size((80, 24)).columns
    target_width = min(74, term_width - 4)

    hud_panel = Panel(
        hud_table,
        title=f"[{accent}] ❖ TELEMETRY CONTROL MATRIX ❖ [/{accent}]",
        border_style=border_col,
        padding=(0, 0),
        width=target_width
    )

    # Center panel dynamically in terminal
    console.print(Align.center(hud_panel))


def print_banner(theme_key="emerald"):
    """
    Renders proportional neon-green block banner followed by centered status HUD matrix.
    """
    term_width = shutil.get_terminal_size((80, 24)).columns

    console.print()
    # 1. Render Centered Neon Green ASCII Banner
    for line in IRIS_BLOCK_BANNER:
        centered_line = line.center(term_width)
        print(f"{NEON_GREEN}{centered_line}{RESET}")

    # 2. Subtitle line
    print(f"{NEON_GREEN}{TAGLINE.center(term_width)}{RESET}")

    # 3. Render Centered Proportional Sci-Fi Status HUD
    render_scifi_status_hud(state="IDLE", theme_key=theme_key)


def render_banner(theme_key="emerald", animate=False):
    """Bridge method for compatibility with CLI callers."""
    print_banner(theme_key=theme_key)


if __name__ == "__main__":
    print_banner()
