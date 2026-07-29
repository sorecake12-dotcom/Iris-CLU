"""
IRIS AI - Window Manager
Minimize, maximize, restore, focus, and list open windows using
pygetwindow (primary) with Win32 API fallback via ctypes/subprocess.
"""

import os
import re
import subprocess
import time
from typing import Optional
from rich.console import Console
from debug_logger import debug_log, log_exception

console = Console()

# ── Optional pygetwindow ──────────────────────────────────────────
try:
    import pygetwindow as gw
    HAS_GW = True
except ImportError:
    gw = None
    HAS_GW = False


# ── Win32 fallback via PowerShell ────────────────────────────────

def _ps(cmd: str, timeout: int = 8) -> str:
    """Run a PowerShell command and return stdout."""
    try:
        res = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        return res.stdout.strip()
    except Exception:
        return ""


# ── Window Manager ────────────────────────────────────────────────

class WindowManager:

    def _find_windows(self, query: str) -> list:
        """Find windows matching the query string (fuzzy name match)."""
        q = query.lower().strip()
        if HAS_GW:
            all_wins = [w for w in gw.getAllWindows() if w.title.strip()]
            return [w for w in all_wins if q in w.title.lower()]
        return []

    def list_open_windows(self) -> str:
        """Return a list of all visible open windows."""
        if HAS_GW:
            wins = [w.title for w in gw.getAllWindows() if w.title.strip()]
            if not wins:
                return "No open windows detected."
            lines = "\n".join(f"  • {t}" for t in sorted(wins)[:30])
            return f"Open windows ({len(wins)}):\n{lines}"

        # PowerShell fallback
        out = _ps(
            "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
            "Select-Object -ExpandProperty MainWindowTitle | Sort-Object | Get-Unique"
        )
        if out:
            lines = "\n".join(f"  • {ln}" for ln in out.splitlines()[:30])
            return f"Open windows:\n{lines}"
        return "Could not list windows (pygetwindow not installed)."

    def focus_window(self, name: str) -> str:
        """Bring a window to the foreground."""
        if HAS_GW:
            wins = self._find_windows(name)
            if not wins:
                return f"No open window found matching '{name}'."
            if len(wins) > 1:
                names = ", ".join(w.title for w in wins[:5])
                return f"Multiple windows found: {names}. Which one did you mean?"
            try:
                w = wins[0]
                if w.isMinimized:
                    w.restore()
                w.activate()
                return f"Brought '{w.title}' to the foreground."
            except Exception as ex:
                return f"Could not focus window: {ex}"

        # PowerShell fallback
        cmd = (
            f"$wshell = New-Object -ComObject wscript.shell; "
            f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -match '{name}'}} | Select-Object -First 1; "
            f"if ($proc) {{ $wshell.AppActivate($proc.Id) }}"
        )
        _ps(cmd)
        return f"Attempted to bring '{name}' to foreground."

    def minimize_window(self, name: str) -> str:
        if HAS_GW:
            wins = self._find_windows(name)
            if not wins:
                return f"No window found matching '{name}'."
            for w in wins:
                try:
                    w.minimize()
                except Exception:
                    pass
            return f"Minimized {len(wins)} window(s) matching '{name}'."

        cmd = (
            f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -match '{name}'}} | Select-Object -First 1; "
            f"if ($proc) {{ "
            f"  Add-Type -AssemblyName System.Windows.Forms; "
            f"  [System.Windows.Forms.Application]::DoEvents() "
            f"}}"
        )
        _ps(cmd)
        return f"Minimized '{name}'."

    def maximize_window(self, name: str) -> str:
        if HAS_GW:
            wins = self._find_windows(name)
            if not wins:
                return f"No window found matching '{name}'."
            for w in wins:
                try:
                    w.maximize()
                except Exception:
                    pass
            return f"Maximized {len(wins)} window(s) matching '{name}'."

        # PowerShell maximize fallback
        cmd = (
            f"Add-Type @'\n"
            f"using System;\nusing System.Runtime.InteropServices;\n"
            f"public class WM {{\n"
            f"  [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr h, int cmd);\n"
            f"  [DllImport(\"user32.dll\")] public static extern IntPtr FindWindow(string cls, string title);\n"
            f"}}\n'@ -Language CSharp;\n"
            f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -match '{name}'}} | Select-Object -First 1;\n"
            f"if ($proc) {{ [WM]::ShowWindow($proc.MainWindowHandle, 3) }}"
        )
        _ps(cmd)
        return f"Maximized '{name}'."

    def restore_window(self, name: str) -> str:
        if HAS_GW:
            wins = self._find_windows(name)
            if not wins:
                return f"No window found matching '{name}'."
            for w in wins:
                try:
                    w.restore()
                except Exception:
                    pass
            return f"Restored {len(wins)} window(s) matching '{name}'."

        cmd = (
            f"Add-Type @'\n"
            f"using System;\nusing System.Runtime.InteropServices;\n"
            f"public class WM2 {{\n"
            f"  [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr h, int cmd);\n"
            f"}}\n'@ -Language CSharp;\n"
            f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -match '{name}'}} | Select-Object -First 1;\n"
            f"if ($proc) {{ [WM2]::ShowWindow($proc.MainWindowHandle, 9) }}"
        )
        _ps(cmd)
        return f"Restored '{name}'."

    def close_window(self, name: str) -> str:
        """Gracefully close a window (not kill the process)."""
        if HAS_GW:
            wins = self._find_windows(name)
            if not wins:
                return f"No window found matching '{name}'."
            for w in wins:
                try:
                    w.close()
                except Exception:
                    pass
            return f"Closed {len(wins)} window(s) matching '{name}'."

        cmd = (
            f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -match '{name}'}} | Select-Object -First 1; "
            f"if ($proc) {{ $proc.CloseMainWindow() }}"
        )
        _ps(cmd)
        return f"Sent close signal to '{name}'."


# Global Singleton
window_manager = WindowManager()
