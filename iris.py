"""
IRIS AI - Futuristic Sci-Fi Terminal Interface Entry Point
Inspired by JARVIS, FRIDAY, and Claude Code.
"""

import sys
import os

# Ensure UTF-8 execution environment on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
from rich.console import Console

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.history import InMemoryHistory

import config
import banner
import ui
from key_manager import ensure_api_keys_configured
from voice_engine import voice_engine
from llm_engine import llm_engine
from commands import CommandProcessor
from task_scheduler import task_scheduler

console = Console()

class IrisCLI:
    def __init__(self, theme=config.DEFAULT_THEME, boot_anim=True):
        self.current_theme = theme if theme in config.THEMES else config.DEFAULT_THEME
        self.boot_anim = boot_anim
        self.processor = CommandProcessor(self)
        self.history = InMemoryHistory()
        # Start background task scheduler engine
        task_scheduler.start()

    def get_completer(self):
        """Build command completer for prompt_toolkit."""
        commands = [
            "/help", "/automation", "/actions", "/status", "/sys", "/sysinfo", "/voice", "/matrix",
            "/timers", "/tasks", "/schedule", "/canceltimer",
            "/theme jarvis", "/theme cyberpunk", "/theme matrix", "/theme solar",
            "/calc", "/time", "/history", "/clear", "/about", "/exit", "quit"
        ]
        return WordCompleter(commands, ignore_case=True)

    def get_prompt_style(self):
        """Prompt toolkit color theme."""
        t = config.THEMES.get(self.current_theme, config.THEMES[config.DEFAULT_THEME])
        primary = t["primary"]

        color_map = {
            "cyan": "#00f0ff",
            "magenta": "#ff007f",
            "green": "#00ff66",
            "yellow": "#ffb700",
            "sky_blue1": "#00aaff",
            "bright_white": "#ffffff"
        }
        brand_color = color_map.get(primary, "#00f0ff")

        return PTStyle.from_dict({
            "brand": f"bold {brand_color}",
            "symbol": "bold #00ffaa",
            "pointer": "bold #ffffff",
        })

    def run(self):
        """Main execution loop for IRIS AI CLI."""
        # Clear screen and render HUD ASCII banner
        console.clear()
        banner.render_banner(theme_key=self.current_theme, animate=self.boot_anim)

        # Initial Conversational AI Greeting
        t = config.THEMES.get(self.current_theme, config.THEMES[config.DEFAULT_THEME])
        accent = t["accent"]
        console.print(f"[{accent}]IRIS AI >[/{accent}]")
        console.print("Hey Boss! What would you like me to do today?\n")

        # Initialize PromptSession
        session = PromptSession(
            history=self.history,
            completer=self.get_completer(),
            complete_while_typing=False
        )

        running = True
        try:
            while running:
                try:
                    user_input = session.prompt(
                        "Boss > ",
                        style=self.get_prompt_style()
                    )
                except (AttributeError, Exception):
                    user_input = input("Boss > ")

                # Interrupt previous audio on new input submit
                voice_engine.stop_speech()

                running = self.processor.process(user_input)

        except KeyboardInterrupt:
            voice_engine.stop_speech()
            console.print("\n[dim cyan]KeyboardInterrupt detected. Use /exit or Ctrl+D to terminate session.[/dim cyan]\n")
        except EOFError:
            voice_engine.stop_speech()
            console.print("\n[bold cyan]Terminating IRIS AI session...[/bold cyan]")
        finally:
            task_scheduler.stop()

def main():
    parser = argparse.ArgumentParser(description="IRIS AI - Futuristic Terminal Interface")
    parser.add_argument("--theme", type=str, default="emerald", choices=["emerald", "jarvis", "cyberpunk", "matrix", "solar"], help="Set visual color theme")
    parser.add_argument("--no-boot", action="store_true", help="Skip startup sequence")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable developer debug mode (live telemetry logs)")

    args = parser.parse_args()

    if args.debug:
        config.DEBUG_MODE = True

    # Ensure API keys are configured before starting (runs wizard on first launch)
    ensure_api_keys_configured()

    app = IrisCLI(theme=args.theme, boot_anim=not args.no_boot)
    app.run()

if __name__ == "__main__":
    main()
