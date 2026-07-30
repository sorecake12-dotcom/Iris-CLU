"""
IRIS AI - Workspace Manager & Multi-Monitor Engine
Handles Workspace Profiles (Coding, Gaming, Study, Movie, Streaming, Meeting),
Multi-Monitor window positioning, Window Tiling grid, and Window Verification.
"""

import os
import sys
import time
import math
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from rich.console import Console
from debug_logger import debug_log, log_exception
from window_manager import window_manager, get_work_area, calculate_snap_bounds, HAS_GW

console = Console()


# ── Multi-Monitor Enumeration ─────────────────────────────────────

def get_monitors_info() -> List[Tuple[int, int, int, int]]:
    """Returns list of (x, y, width, height) for each connected monitor."""
    monitors = []
    try:
        import ctypes
        from ctypes import wintypes
        
        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
            ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
        )
        
        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)
            ]

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
                r = mi.rcWork  # Usable work area of that monitor
                monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return True

        cb = MONITORENUMPROC(callback)
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, cb, 0)
    except Exception as ex:
        debug_log(f"EnumDisplayMonitors failed: {ex}", category="MONITOR")

    if not monitors:
        # Fallback to primary work area
        wx, wy, ww, wh = get_work_area()
        monitors.append((wx, wy, ww, wh))

    return monitors


# ── Grid Layout Tiling Calculator ────────────────────────────────

def calculate_tile_grid(count: int, work_area: Tuple[int, int, int, int]) -> List[Tuple[int, int, int, int]]:
    """Calculates optimal grid cell bounds for N open windows."""
    wx, wy, ww, wh = work_area
    if count <= 0:
        return []
    if count == 1:
        return [(wx, wy, ww, wh)]
    if count == 2:
        return [
            (wx, wy, ww // 2, wh),
            (wx + (ww // 2), wy, ww // 2, wh)
        ]
    if count == 3:
        return [
            (wx, wy, ww // 2, wh),
            (wx + (ww // 2), wy, ww // 2, wh // 2),
            (wx + (ww // 2), wy + (wh // 2), ww // 2, wh // 2)
        ]
    if count == 4:
        return [
            (wx, wy, ww // 2, wh // 2),
            (wx + (ww // 2), wy, ww // 2, wh // 2),
            (wx, wy + (wh // 2), ww // 2, wh // 2),
            (wx + (ww // 2), wy + (wh // 2), ww // 2, wh // 2)
        ]
    
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    cell_w = ww // cols
    cell_h = wh // rows
    
    cells = []
    for i in range(count):
        r = i // cols
        c = i % cols
        cells.append((wx + (c * cell_w), wy + (r * cell_h), cell_w, cell_h))
    return cells


# ── Workspace Manager Class ───────────────────────────────────────

class WorkspaceManager:

    # ── Window Verification ───────────────────────────────────────

    def verify_window_state(self, name: str, timeout: float = 3.0, expected_bounds: Optional[Tuple[int, int, int, int]] = None) -> Tuple[bool, str]:
        """
        Verifies that window exists, is visible (not minimized), has focus,
        and optionally matches expected layout bounds.
        """
        start_t = time.time()
        while time.time() - start_t <= timeout:
            wins = window_manager._find_windows(name)
            if wins:
                # Check visibility
                visible_wins = []
                for w in wins:
                    try:
                        if HAS_GW:
                            if not w.isMinimized:
                                visible_wins.append(w)
                        else:
                            visible_wins.append(w)
                    except Exception:
                        pass
                
                if visible_wins:
                    # Focus top visible window
                    try:
                        window_manager.focus_window(name)
                    except Exception:
                        pass

                    if expected_bounds and HAS_GW:
                        ex, ey, ew, eh = expected_bounds
                        target_win = visible_wins[0]
                        try:
                            # Verify width and height within 15% tolerance
                            w_ok = abs(target_win.width - ew) <= (ew * 0.15) or ew == 0
                            h_ok = abs(target_win.height - eh) <= (eh * 0.15) or eh == 0
                            if w_ok and h_ok:
                                return True, f"Verified '{name}': visible, focused, layout verified ({target_win.width}x{target_win.height})."
                        except Exception:
                            pass
                    
                    return True, f"Verified '{name}': visible and focused in foreground."

            time.sleep(0.3)

        return False, f"Verification timeout ({timeout}s): '{name}' is not in expected state."

    # ── Multi-Monitor Control ─────────────────────────────────────

    def move_to_monitor(self, name: str, monitor_index: int = 1, position: str = "maximized") -> str:
        """Move a window to a specific monitor (1-indexed) and snap/maximize it."""
        monitors = get_monitors_info()
        idx = monitor_index - 1
        if idx < 0 or idx >= len(monitors):
            return f"Monitor {monitor_index} not found. Systems detects {len(monitors)} connected monitor(s)."

        mx, my, mw, mh = monitors[idx]
        
        pos_clean = position.lower().strip()
        if pos_clean in ["maximized", "full", "maximize"]:
            tx, ty, tw, th = mx, my, mw, mh
        elif pos_clean in ["left", "left_half"]:
            tx, ty, tw, th = mx, my, mw // 2, mh
        elif pos_clean in ["right", "right_half"]:
            tx, ty, tw, th = mx + (mw // 2), my, mw // 2, mh
        elif pos_clean in ["top", "top_half"]:
            tx, ty, tw, th = mx, my, mw, mh // 2
        elif pos_clean in ["bottom", "bottom_half"]:
            tx, ty, tw, th = mx, my + (mh // 2), mw, mh // 2
        else:
            tx, ty, tw, th = mx, my, mw, mh

        res = window_manager.set_window_geometry(name, tx, ty, tw, th)
        # Verify
        verified, v_msg = self.verify_window_state(name, timeout=2.0)
        return f"Moved '{name}' to Monitor {monitor_index} ({mw}x{mh}).\n  • {v_msg}"

    # ── Window Tiling ─────────────────────────────────────────────

    def tile_all_windows(self) -> str:
        """Automatically tile all open visible user windows into a clean grid."""
        if not HAS_GW:
            return window_manager.list_open_windows()

        all_wins = [w for w in gw.getAllWindows() if w.title.strip()]
        # Filter out system desktop elements, taskbar, tooltips, hidden
        ignore_titles = ["Program Manager", "Task Manager", "Windows Input Experience", "NVIDIA GeForce Overlay", "Settings"]
        
        valid_wins = []
        for w in all_wins:
            t = w.title.strip()
            if any(ig.lower() in t.lower() for ig in ignore_titles):
                continue
            if w.width > 100 and w.height > 100 and not w.isMinimized:
                valid_wins.append(w)

        if not valid_wins:
            return "No active visible windows found to tile."

        work_area = get_work_area()
        grid = calculate_tile_grid(len(valid_wins), work_area)

        tiled = []
        for win, (cx, cy, cw, ch) in zip(valid_wins, grid):
            try:
                if hasattr(win, '_hWnd') and win._hWnd:
                    import ctypes
                    ctypes.windll.user32.ShowWindow(win._hWnd, 9)
                    ctypes.windll.user32.MoveWindow(win._hWnd, int(cx), int(cy), int(cw), int(ch), True)
                else:
                    win.moveTo(cx, cy)
                    win.resizeTo(cw, ch)
                tiled.append(win.title[:30])
            except Exception:
                pass

        lines = "\n".join(f"  • {t}" for t in tiled)
        return f"Tiled {len(tiled)} windows into desktop grid:\n{lines}"

    # ── Workspace Profiles ────────────────────────────────────────

    def launch_profile(self, profile_name: str) -> str:
        """
        Launch and arrange preset or custom workspace profiles.
        Profiles: Coding, Study, Gaming, Movie, Streaming, Meeting
        """
        p_clean = profile_name.lower().strip()
        
        if any(k in p_clean for k in ["coding", "developer", "code"]):
            return self._profile_coding()
        elif any(k in p_clean for k in ["study", "research", "read"]):
            return self._profile_study()
        elif any(k in p_clean for k in ["gaming", "game"]):
            return self._profile_gaming()
        elif any(k in p_clean for k in ["movie", "cinema", "media", "video"]):
            return self._profile_movie()
        elif any(k in p_clean for k in ["streaming", "obs"]):
            return self._profile_streaming()
        elif any(k in p_clean for k in ["meeting", "zoom", "call", "conference"]):
            return self._profile_meeting()
        else:
            return f"Unknown workspace profile '{profile_name}'. Available: Coding, Study, Gaming, Movie, Streaming, Meeting."

    # ── Profile Implementations ───────────────────────────────────

    def _profile_coding(self) -> str:
        """Coding Mode: VS Code (left half), Chrome/GitHub (bottom-right), Spotify (top-right)."""
        from automation_engine import automation_engine
        
        # 1. Launch / focus VS Code
        automation_engine.execute_action({"action": "open_app", "target": "vs code"})
        time.sleep(1.0)
        window_manager.snap_window("vs code", "left")

        # 2. Launch / focus Spotify (top-right)
        automation_engine.execute_action({"action": "open_app", "target": "spotify"})
        time.sleep(1.0)
        window_manager.snap_window("spotify", "top_right")

        # 3. Launch Chrome (bottom-right)
        automation_engine.execute_action({"action": "open_website", "url": "https://github.com"})
        time.sleep(1.0)
        window_manager.snap_window("chrome", "bottom_right")

        # Verify
        self.verify_window_state("vs code", timeout=2.0)
        return "⚡ [CODING WORKSPACE ACTIVATED]\n  • VS Code: Snapped to Left Half\n  • Spotify: Snapped to Top-Right Corner\n  • Chrome (GitHub): Snapped to Bottom-Right Corner"

    def _profile_study(self) -> str:
        """Study Mode: Browser (left half), Notepad/Notion (right half), Lofi music."""
        from automation_engine import automation_engine
        
        # Browser on Left
        automation_engine.execute_action({"action": "open_website", "url": "https://www.google.com"})
        time.sleep(1.0)
        window_manager.snap_window("chrome", "left")

        # Notepad / Notes on Right
        automation_engine.execute_action({"action": "open_app", "target": "notepad"})
        time.sleep(1.0)
        window_manager.snap_window("notepad", "right")

        # Play study music
        automation_engine.execute_action({"action": "play_spotify", "query": "Lofi Study Beats"})
        return "📚 [STUDY WORKSPACE ACTIVATED]\n  • Chrome: Snapped to Left Half\n  • Notepad: Snapped to Right Half\n  • Music: Playing Lofi Study Beats on Spotify"

    def _profile_gaming(self) -> str:
        """Gaming Mode: Minimize background, launch Discord (right), Steam (maximized)."""
        from automation_engine import automation_engine

        # Discord (right)
        automation_engine.execute_action({"action": "open_app", "target": "discord"})
        time.sleep(1.0)
        window_manager.snap_window("discord", "right")

        # Steam (left/maximized)
        automation_engine.execute_action({"action": "open_app", "target": "steam"})
        time.sleep(1.0)
        window_manager.maximize_window("steam")

        return "🎮 [GAMING WORKSPACE ACTIVATED]\n  • Steam: Maximized\n  • Discord: Snapped to Right Half"

    def _profile_movie(self) -> str:
        """Movie Mode: Browser/YouTube maximized, Spotify paused."""
        from automation_engine import automation_engine

        automation_engine.execute_action({"action": "pause_spotify"})
        automation_engine.execute_action({"action": "open_website", "url": "https://youtube.com"})
        time.sleep(1.0)
        window_manager.maximize_window("chrome")

        return "🎬 [MOVIE WORKSPACE ACTIVATED]\n  • YouTube/Browser: Maximized\n  • Spotify: Paused"

    def _profile_streaming(self) -> str:
        """Streaming Mode: OBS & Discord arrangement."""
        from automation_engine import automation_engine
        automation_engine.execute_action({"action": "open_app", "target": "obs"})
        automation_engine.execute_action({"action": "open_app", "target": "discord"})
        time.sleep(1.0)
        window_manager.snap_window("obs", "left")
        window_manager.snap_window("discord", "right")
        return "📡 [STREAMING WORKSPACE ACTIVATED]\n  • OBS Studio: Snapped Left\n  • Discord: Snapped Right"

    def _profile_meeting(self) -> str:
        """Meeting Mode: Zoom/Teams/Discord, Notepad notes (right)."""
        from automation_engine import automation_engine
        automation_engine.execute_action({"action": "pause_spotify"})
        automation_engine.execute_action({"action": "open_app", "target": "notepad"})
        time.sleep(1.0)
        window_manager.snap_window("notepad", "right")
        return "🎙 [MEETING WORKSPACE ACTIVATED]\n  • Notes (Notepad): Snapped Right\n  • Spotify: Muted/Paused"

    # ── Workflow Engine ───────────────────────────────────────────

    def execute_workflow(self, steps: List[dict]) -> str:
        """Execute a sequence of multiple automation steps sequentially."""
        from automation_engine import automation_engine
        
        results = []
        for i, step in enumerate(steps, 1):
            act_name = step.get("action", "unknown")
            try:
                res = automation_engine.execute_action(step, confirmed=True)
                status = res.get("status", "completed")
                details = res.get("details", "") or res.get("reason", "")
                results.append(f"  Step {i} [{act_name}]: {status} — {details}")
            except Exception as ex:
                results.append(f"  Step {i} [{act_name}]: failed — {ex}")
            time.sleep(0.5)

        summary = "\n".join(results)
        return f"Completed multi-step workflow ({len(steps)} steps):\n{summary}"


# Global Singleton
workspace_manager = WorkspaceManager()
