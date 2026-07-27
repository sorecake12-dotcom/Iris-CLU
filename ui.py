"""
IRIS AI UI & Formatting Utilities
Futuristic Sci-Fi Developer Interface inspired by JARVIS, FRIDAY, Claude Code, and Gemini.
"""

import sys
import time
import random
import os
import re
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text

import config
from voice_engine import voice_engine

console = Console()


def play_audio_beep(frequency=1200, duration_ms=60):
    """Play a short futuristic synth beep when user submits input or starts command."""
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(frequency, duration_ms)
        else:
            print("\a", end="", flush=True)
    except Exception:
        pass


def strip_json_blocks(text: str) -> str:
    """Remove internal JSON action code blocks from text rendered to user on screen."""
    if not text:
        return ""
    clean = re.sub(r"```json\s*[\s\S]*?\s*```", "", text, flags=re.IGNORECASE)
    clean = re.sub(r"\{\s*\"action\"\s*:\s*\"[^\"]+\"[\s\S]*?\}", "", clean)
    return clean.strip()


def render_streaming_response(generator, title="IRIS AI", theme_key="emerald", speak=True) -> str:
    """
    Streams response from LLM generator in real-time.
    In normal mode: displays clean conversational chat layout (IRIS AI > ...) without boxes/panels.
    In debug mode: renders telemetry logs and bordered panels.
    """
    t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])
    accent = t["accent"]

    play_audio_beep(frequency=1200, duration_ms=60)
    console.print()

    full_text = ""

    # Phase 1: Subtle Thinking Indicator
    with console.status("[dim cyan]● Thinking...[/dim cyan]", spinner="dots"):
        try:
            for chunk in generator:
                full_text += chunk
                if full_text.strip():
                    break
        except Exception as e:
            console.print(f"[bold red]Error connecting stream:[/bold red] {e}")
            return ""

    if not full_text.strip():
        console.print("[dim red]No response tokens received from AI engine.[/dim red]")
        return ""

    # Phase 2: Conversational Streaming Output (No Bordered Boxes/Panels in Normal Mode)
    if not config.DEBUG_MODE:
        console.print(f"[{accent}]IRIS AI >[/{accent}]")

        def make_chat_renderable(content_text):
            display_text = strip_json_blocks(content_text)
            if not display_text:
                return Text("Processing request...")
            return Markdown(display_text)

        try:
            with Live(make_chat_renderable(full_text), console=console, refresh_per_second=16) as live:
                for chunk in generator:
                    full_text += chunk
                    live.update(make_chat_renderable(full_text))
        except Exception:
            display_text = strip_json_blocks(full_text)
            if display_text:
                console.print(Markdown(display_text))

        console.print()
    else:
        # Debug Mode Panel View
        header_title = f"[{accent}]✦ IRIS AI (DEBUG)[/{accent}]"
        def make_panel_renderable(content_text):
            display_text = strip_json_blocks(content_text)
            return Panel(Markdown(display_text or "Processing..."), title=header_title, border_style=t["border"], padding=(0, 1))

        try:
            with Live(make_panel_renderable(full_text), console=console, refresh_per_second=16) as live:
                for chunk in generator:
                    full_text += chunk
                    live.update(make_panel_renderable(full_text))
        except Exception:
            console.print(make_panel_renderable(full_text))
        console.print()

    # Phase 3: Trigger Audio Playback
    if speak and full_text.strip():
        spoken_text = strip_json_blocks(full_text)
        if spoken_text:
            voice_engine.speak(spoken_text)

    return full_text


def print_matrix_rain(duration=3.5):
    """Futuristic Matrix digital rain visualizer."""
    console.clear()
    console.print("[bold green]INITIALIZING MATRIX DATA STREAM... Press Ctrl+C to stop.[/bold green]\n")

    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@#$%&*§µΞΨΩ"
    width = os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 80
    drops = [0] * width

    start_time = time.time()
    try:
        while time.time() - start_time < duration:
            line = []
            for i in range(width):
                if random.random() > 0.94:
                    drops[i] = 0

                if drops[i] < 15 and random.random() > 0.3:
                    char = random.choice(chars)
                    if drops[i] == 0:
                        line.append(f"[bold white]{char}[/bold white]")
                    elif drops[i] < 5:
                        line.append(f"[bold green]{char}[/bold green]")
                    else:
                        line.append(f"[dim green]{char}[/dim green]")
                    drops[i] += 1
                else:
                    line.append(" ")

            console.print("".join(line), highlight=False)
            time.sleep(0.04)
    except KeyboardInterrupt:
        pass

    console.clear()
    console.print("[bold cyan]DATA STREAM COMPLETED. RETURNING TO IRIS CORE.[/bold cyan]\n")


def print_error(msg):
    """Format compact error message panel."""
    console.print(Panel(f"[bold red]ERROR:[/bold red] {msg}", border_style="red", title="[bold red]SYSTEM ALERT[/bold red]", padding=(0, 1)))


def print_info(title, msg, theme_key="emerald"):
    """Format compact info message panel."""
    t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])
    console.print(Panel(msg, border_style=t["border"], title=f"[{t['accent']}]{title}[/{t['accent']}]", padding=(0, 1)))


def render_action_telemetry(result_data: dict, theme_key="emerald"):
    """Format and render action execution results."""
    t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])
    status = result_data.get("status", "unknown")
    action = result_data.get("action", "desktop_automation")

    if config.DEBUG_MODE:
        if status == "success":
            details = result_data.get("details", "Action executed successfully.")
            body = f"[bold green]✓ ACTION EXECUTED: {action}[/bold green]\n\n{details}"
            console.print(Panel(body, border_style=t["border"], title=f"[{t['accent']}]✦ WINDOWS AUTOMATION ENGINE[/{t['accent']}]", padding=(0, 1)))
        elif status == "failed":
            reason = result_data.get("reason", "Unknown error")
            body = f"[bold red]✗ ACTION FAILED: {action}[/bold red]\n\nReason: {reason}"
            console.print(Panel(body, border_style="red", title="[bold red]✦ AUTOMATION ALERT[/bold red]", padding=(0, 1)))
    else:
        if status == "success":
            details = result_data.get("details", "Action completed.")
            console.print(f"[dim green]● {details}[/dim green]\n")
        elif status == "failed":
            reason = result_data.get("reason", "Action could not be completed.")
            console.print(f"[dim red]● Notice: {reason}[/dim red]\n")


def render_scheduled_tasks_table(tasks: list, theme_key="emerald"):
    """Render structured table of active timers and scheduled tasks."""
    t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])
    accent = t["accent"]

    if not tasks:
        console.print("[dim cyan]● No active timers or scheduled tasks currently running.[/dim cyan]\n")
        return

    table = Table(title=f"[{accent}][:: ACTIVE SCHEDULER & TIMER ENGINE ::][/{accent}]", border_style=t["border"])
    table.add_column("Task ID", style=f"bold {accent}", no_wrap=True)
    table.add_column("Type", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Status", style="bold yellow")
    table.add_column("Time Left", style="bold green")
    table.add_column("Target Execution", style="dim white")

    for task in tasks:
        d = task.to_dict() if hasattr(task, "to_dict") else task
        table.add_row(
            d.get("id", ""),
            d.get("type", "").upper(),
            d.get("description", ""),
            d.get("status", "").upper(),
            d.get("time_left", ""),
            d.get("target_time", "")
        )

    console.print(table)
    console.print()

