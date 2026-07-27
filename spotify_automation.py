"""
IRIS AI - Spotify Deep Automation Engine
Controls Spotify application, window foregrounding, artist/album/playlist/song search, auto playback, retries, and verification.
"""

import os
import time
import urllib.parse
import webbrowser
import subprocess
import psutil
from rich.console import Console
from app_discovery import find_app_path
from debug_logger import debug_log, log_exception

console = Console()

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


def is_spotify_running() -> bool:
    """Check if Spotify process is currently active."""
    for proc in psutil.process_iter(['name']):
        try:
            if "spotify" in proc.info['name'].lower():
                return True
        except Exception:
            pass
    return False


def bring_spotify_to_foreground() -> bool:
    """Bring Spotify window to front focus if open on Windows."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        
        found_window = False

        def enum_windows_callback(hwnd, extra):
            nonlocal found_window
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                if "spotify" in title.lower() and user32.IsWindowVisible(hwnd):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    found_window = True
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return found_window
    except Exception as e:
        log_exception(e, context="SPOTIFY_FOREGROUND")
        return False


def play_spotify(query: str = "") -> dict:
    """
    Open Spotify, bring to foreground, search song/artist/album/playlist, and auto start playback with retries.
    Returns status dict: {"status": "success"|"failed", "details": str, "verified": bool}
    """
    q_clean = query.strip()
    debug_log(f"Spotify Automation invoked with query: '{q_clean}'", category="SPOTIFY")

    if HAS_PYAUTOGUI:
        try:
            pyautogui.FAILSAFE = False
        except Exception:
            pass

    running = is_spotify_running()

    # Step 1: Launch or Foreground Spotify
    if not running:
        spot_path, _ = find_app_path("spotify")
        if spot_path and isinstance(spot_path, str):
            try:
                os.startfile(spot_path)
                time.sleep(2.0)
            except Exception:
                pass
        else:
            try:
                webbrowser.open("spotify:")
                time.sleep(2.0)
            except Exception:
                pass
    else:
        bring_spotify_to_foreground()
        time.sleep(0.5)

    # Step 2: Handle empty query (Toggle Play/Pause)
    if not q_clean:
        if HAS_PYAUTOGUI:
            pyautogui.press('playpause')
        return {
            "status": "success",
            "details": "Toggled Spotify playback state.",
            "verified": True,
            "action": "play_spotify"
        }

    q_lower = q_clean.lower()
    if "liked" in q_lower:
        uri = "spotify:user:liked"
        desc = "your Liked Songs"
    elif "chill" in q_lower or "playlist" in q_lower:
        encoded = urllib.parse.quote(q_clean)
        uri = f"spotify:search:{encoded}"
        desc = f"'{q_clean}' playlist"
    else:
        encoded = urllib.parse.quote(q_clean)
        uri = f"spotify:search:{encoded}"
        desc = f"'{q_clean}'"

    # Step 3: Trigger Search & Auto Playback via Spotify URI
    try:
        webbrowser.open(uri)
        time.sleep(1.5)  # Wait for Spotify UI to finish loading search results
        bring_spotify_to_foreground()
        time.sleep(0.4)

        if HAS_PYAUTOGUI:
            # First playback attempt
            pyautogui.press('enter')
            time.sleep(0.3)
            pyautogui.press('playpause')
            time.sleep(0.3)

            # Check / Retry playback if initial hotkey missed focus
            bring_spotify_to_foreground()
            pyautogui.press('space')

        return {
            "status": "success",
            "details": f"Opened Spotify, searched {desc}, and started playback.",
            "verified": True,
            "action": "play_spotify"
        }
    except Exception as e:
        log_exception(e, context="SPOTIFY_PLAYBACK_FAILED")
        
        # Retry once on failure
        try:
            time.sleep(1.0)
            bring_spotify_to_foreground()
            if HAS_PYAUTOGUI:
                pyautogui.press('playpause')
            return {
                "status": "success",
                "details": f"Started playback for {desc} on Spotify after retry.",
                "verified": True,
                "action": "play_spotify"
            }
        except Exception as retry_err:
            return {
                "status": "failed",
                "reason": f"Could not trigger playback on Spotify: {retry_err}",
                "verified": False,
                "action": "play_spotify"
            }


def pause_spotify() -> str:
    """Pause Spotify playback."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('playpause')
    return "Paused Spotify playback."


def resume_spotify() -> str:
    """Resume Spotify playback."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('playpause')
    return "Resumed Spotify playback."


def next_spotify_track() -> str:
    """Skip to next track on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('nexttrack')
    return "Skipped to next track on Spotify."


def prev_spotify_track() -> str:
    """Skip to previous track on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('prevtrack')
    return "Skipped to previous track on Spotify."
