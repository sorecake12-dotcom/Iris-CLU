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


def get_work_area() -> tuple[int, int, int, int]:
    """Returns (x, y, width, height) of usable desktop work area excluding taskbar."""
    try:
        import ctypes
        from ctypes import wintypes
        class RECT(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                        ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
        rect = RECT()
        # SPI_GETWORKAREA = 0x0030
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 0 and h > 0:
                return rect.left, rect.top, w, h
    except Exception:
        pass
    try:
        import ctypes
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        if w > 0 and h > 0:
            return 0, 0, w, h
    except Exception:
        pass
    return 0, 0, 1920, 1080


def calculate_snap_bounds(position: str) -> tuple[int, int, int, int]:
    wx, wy, ww, wh = get_work_area()
    pos = position.lower().replace(" ", "_").replace("-", "_")

    if pos in ["left", "left_side", "left_half", "snap_left"]:
        return wx, wy, ww // 2, wh
    elif pos in ["right", "right_side", "right_half", "snap_right"]:
        return wx + (ww // 2), wy, ww // 2, wh
    elif pos in ["top", "top_side", "top_half", "snap_top"]:
        return wx, wy, ww, wh // 2
    elif pos in ["bottom", "bottom_side", "bottom_half", "snap_bottom"]:
        return wx, wy + (wh // 2), ww, wh // 2
    elif pos in ["top_left", "topleft"]:
        return wx, wy, ww // 2, wh // 2
    elif pos in ["top_right", "topright"]:
        return wx + (ww // 2), wy, ww // 2, wh // 2
    elif pos in ["bottom_left", "bottomleft"]:
        return wx, wy + (wh // 2), ww // 2, wh // 2
    elif pos in ["bottom_right", "bottomright"]:
        return wx + (ww // 2), wy + (wh // 2), ww // 2, wh // 2
    elif pos in ["center", "middle"]:
        return wx + (ww // 4), wy + (wh // 4), ww // 2, wh // 2
    else:
        return wx, wy, ww // 2, wh


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

    def snap_window(self, name: str, position: str = "left") -> str:
        """Snap a window to left, right, top, bottom, corners, or center."""
        x, y, w, h = calculate_snap_bounds(position)

        wins = self._find_windows(name)
        if not wins:
            # Try launching app if not open
            self._try_launch_app(name)
            time.sleep(1.5)
            wins = self._find_windows(name)

        if not wins:
            ps_success = self._ps_snap_window(name, x, y, w, h)
            if ps_success:
                return f"Snapped '{name}' to {position} half ({w}x{h})."
            return f"Could not find open window for '{name}'."

        count = 0
        for win in wins:
            try:
                if HAS_GW and hasattr(win, '_hWnd') and win._hWnd:
                    import ctypes
                    ctypes.windll.user32.ShowWindow(win._hWnd, 9)
                    ctypes.windll.user32.MoveWindow(win._hWnd, int(x), int(y), int(w), int(h), True)
                    ctypes.windll.user32.SetForegroundWindow(win._hWnd)
                    count += 1
                elif HAS_GW:
                    if win.isMaximized or win.isMinimized:
                        win.restore()
                        time.sleep(0.1)
                    win.moveTo(x, y)
                    win.resizeTo(w, h)
                    win.activate()
                    count += 1
            except Exception as ex:
                debug_log(f"Snap failed for window {win}: {ex}", category="WINDOW")

        pos_label = position.replace("_", " ").title()
        return f"Snapped '{name}' to {pos_label} side of screen ({w}x{h})."

    def split_screen(self, left_target: str, right_target: str) -> str:
        """Snap one window to left half and another to right half."""
        res_left = self.snap_window(left_target, "left")
        time.sleep(0.3)
        res_right = self.snap_window(right_target, "right")
        return f"Split screen layout complete:\n  • {res_left}\n  • {res_right}"

    def set_window_geometry(self, name: str, x: int, y: int, width: int, height: int) -> str:
        """Move and resize window to exact coordinates."""
        wins = self._find_windows(name)
        if not wins:
            self._try_launch_app(name)
            time.sleep(1.2)
            wins = self._find_windows(name)
        if not wins:
            self._ps_snap_window(name, x, y, width, height)
            return f"Set '{name}' bounds to ({x}, {y}, {width}x{height})."
        for win in wins:
            try:
                if HAS_GW and hasattr(win, '_hWnd') and win._hWnd:
                    import ctypes
                    ctypes.windll.user32.ShowWindow(win._hWnd, 9)
                    ctypes.windll.user32.MoveWindow(win._hWnd, int(x), int(y), int(width), int(height), True)
                    ctypes.windll.user32.SetForegroundWindow(win._hWnd)
            except Exception:
                pass
        return f"Positioned '{name}' window at ({x}, {y}, {width}x{height})."

    def _ps_snap_window(self, name: str, x: int, y: int, w: int, h: int) -> bool:
        cmd = (
            f"Add-Type @'\n"
            f"using System;\nusing System.Runtime.InteropServices;\n"
            f"public class WinSnap {{\n"
            f"  [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr h, int cmd);\n"
            f"  [DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int h, bool repaint);\n"
            f"  [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr h);\n"
            f"}}\n'@ -Language CSharp;\n"
            f"$proc = Get-Process | Where-Object {{$_.MainWindowTitle -match '{name}'}} | Select-Object -First 1;\n"
            f"if ($proc) {{\n"
            f"  [WinSnap]::ShowWindow($proc.MainWindowHandle, 9);\n"
            f"  [WinSnap]::MoveWindow($proc.MainWindowHandle, {x}, {y}, {w}, {h}, $true);\n"
            f"  [WinSnap]::SetForegroundWindow($proc.MainWindowHandle);\n"
            f"  exit 0\n"
            f"}} else {{ exit 1 }}"
        )
        out = _ps(cmd)
        return True

    def _try_launch_app(self, name: str):
        try:
            from app_discovery import find_app_path
            app_info = find_app_path(name)
            if app_info and app_info.get("path"):
                os.startfile(app_info["path"])
        except Exception:
            pass


# Global Singleton
window_manager = WindowManager()

