"""
IRIS AI - Clipboard Engine
Full clipboard management: read, write, clear, rolling history,
background monitoring thread. Uses pyperclip + Win32 fallback.
"""

import os
import time
import threading
from collections import deque
from rich.console import Console
from rich.table import Table
from rich import box
from debug_logger import debug_log, log_exception

console = Console()

HISTORY_LIMIT = 20   # number of recent clipboard entries to remember

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    pyperclip = None
    HAS_PYPERCLIP = False

# Win32 fallback for read via PowerShell
import subprocess

def _ps_read() -> str:
    try:
        res = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        return res.stdout.strip()
    except Exception:
        return ""

def _ps_write(text: str):
    try:
        escaped = text.replace("'", "''")
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value '{escaped}'"],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
    except Exception:
        pass


class ClipboardEngine:

    def __init__(self):
        self._history: deque[str] = deque(maxlen=HISTORY_LIMIT)
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitor = threading.Event()
        self._last_seen    = ""

    # ── Core Operations ───────────────────────────────────────────

    def read(self) -> str:
        """Read current clipboard content."""
        if HAS_PYPERCLIP:
            try:
                text = pyperclip.paste()
                if text and text != self._last_seen:
                    self._history.append(text)
                    self._last_seen = text
                return f'Clipboard: "{text[:500]}"' if text else "Clipboard is empty."
            except Exception:
                pass
        text = _ps_read()
        return f'Clipboard: "{text[:500]}"' if text else "Clipboard is empty."

    def write(self, text: str) -> str:
        """Write text to clipboard."""
        if HAS_PYPERCLIP:
            try:
                pyperclip.copy(text)
                self._history.append(text)
                self._last_seen = text
                return f"Copied {len(text)} characters to clipboard."
            except Exception:
                pass
        _ps_write(text)
        self._history.append(text)
        return f"Copied to clipboard: \"{text[:80]}\""

    def clear(self) -> str:
        """Clear the clipboard."""
        if HAS_PYPERCLIP:
            try:
                pyperclip.copy("")
                return "Clipboard cleared."
            except Exception:
                pass
        _ps_write("")
        return "Clipboard cleared."

    def get_raw(self) -> str:
        """Return raw clipboard text (no formatting)."""
        if HAS_PYPERCLIP:
            try:
                return pyperclip.paste() or ""
            except Exception:
                pass
        return _ps_read()

    # ── History ───────────────────────────────────────────────────

    def get_history(self) -> list[str]:
        return list(self._history)

    def print_history(self, theme_key: str = "emerald"):
        """Display clipboard history in a Rich table."""
        import config
        t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])

        entries = list(self._history)
        if not entries:
            console.print("[dim yellow]  No clipboard history recorded yet.[/dim yellow]\n")
            return

        table = Table(
            title="[bold cyan][::] CLIPBOARD HISTORY [::][/bold cyan]",
            border_style=t["border"], box=box.ROUNDED
        )
        table.add_column("#",       style="dim",          no_wrap=True, width=4)
        table.add_column("Content", style="white")
        table.add_column("Length",  style="dim",          no_wrap=True)

        for i, entry in enumerate(reversed(entries), 1):
            preview = entry[:80].replace("\n", "↵") + ("..." if len(entry) > 80 else "")
            table.add_row(str(i), preview, str(len(entry)))

        console.print()
        console.print(table)
        console.print(f"[dim]  {len(entries)} recent entries. Run /clip [N] to copy entry N back to clipboard.[/dim]\n")

    def recall(self, index: int) -> str:
        """Copy a history entry back to the clipboard (1 = most recent)."""
        entries = list(reversed(list(self._history)))
        if index < 1 or index > len(entries):
            return f"No history entry #{index}. You have {len(entries)} entries."
        text = entries[index - 1]
        self.write(text)
        return f"Restored clipboard entry #{index}: \"{text[:80]}\""

    # ── Background Monitor ────────────────────────────────────────

    def start_monitoring(self):
        """Start background thread to track clipboard changes automatically."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="IrisClipboardMonitor"
        )
        self._monitor_thread.start()
        debug_log("Clipboard monitor started", category="CLIPBOARD")

    def stop_monitoring(self):
        self._stop_monitor.set()

    def _monitor_loop(self):
        while not self._stop_monitor.is_set():
            try:
                current = self.get_raw()
                if current and current != self._last_seen and len(current) < 100_000:
                    self._history.append(current)
                    self._last_seen = current
                    debug_log(f"Clipboard changed: {len(current)} chars", category="CLIPBOARD")
            except Exception:
                pass
            time.sleep(1.5)


# Global Singleton
clipboard_engine = ClipboardEngine()
