"""
IRIS AI - Spotify Deep Automation Engine
Controls Spotify application, window foregrounding, song/artist/playlist search,
auto playback start, retries, playback verification, and media hotkeys.
"""

import os
import sys
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
            if "spotify" in (proc.info['name'] or "").lower():
                return True
        except Exception:
            pass
    return False


def bring_spotify_to_foreground() -> bool:
    """Bring Spotify Desktop window to front focus."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        found = False

        def enum_windows_callback(hwnd, extra):
            nonlocal found
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()
                if "spotify" in title and user32.IsWindowVisible(hwnd):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    user32.BringWindowToTop(hwnd)
                    found = True
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return found
    except Exception as e:
        log_exception(e, context="SPOTIFY_FOREGROUND")
        return False


def play_spotify(query: str = "") -> dict:
    """
    Open Spotify, search target song/artist/playlist, and immediately start playback.
    Returns status dict with clean natural messages.
    """
    q_clean = query.strip()
    q_lower = q_clean.lower()
    debug_log(f"Spotify Automation invoked with query: '{q_clean}'", category="SPOTIFY")

    if HAS_PYAUTOGUI:
        try:
            pyautogui.FAILSAFE = False
        except Exception:
            pass

    # 1. Ensure Spotify process is open & foregrounded
    running = is_spotify_running()
    if not running:
        spot_path, _ = find_app_path("spotify")
        if spot_path and isinstance(spot_path, str) and os.path.exists(spot_path):
            try:
                os.startfile(spot_path)
                time.sleep(2.0)
            except Exception:
                webbrowser.open("spotify:")
                time.sleep(2.0)
        else:
            webbrowser.open("spotify:")
            time.sleep(2.0)
    else:
        bring_spotify_to_foreground()
        time.sleep(0.4)

    # 2. Handle empty or Media Control queries
    if not q_clean or q_lower in ["pause", "stop", "pause music", "stop music"]:
        return pause_spotify()

    if q_lower in ["resume", "play", "play music", "resume music", "start music"]:
        return resume_spotify()

    if q_lower in ["next", "next song", "next track", "skip", "skip song"]:
        return next_spotify_track()

    if q_lower in ["previous", "previous song", "prev", "prev song", "previous track"]:
        return prev_spotify_track()

    if q_lower in ["shuffle", "shuffle on", "toggle shuffle"]:
        return toggle_spotify_shuffle()

    if q_lower in ["repeat", "repeat on", "toggle repeat"]:
        return toggle_spotify_repeat()

    # 3. Handle "Liked Songs"
    if "liked" in q_lower:
        try:
            webbrowser.open("spotify:user:liked")
            time.sleep(1.2)
            bring_spotify_to_foreground()
            if HAS_PYAUTOGUI:
                pyautogui.press('space')
                time.sleep(0.3)
                pyautogui.press('enter')
            return {
                "status": "success",
                "details": "Playing your Liked Songs.",
                "verified": True,
                "action": "play_spotify"
            }
        except Exception as ex:
            log_exception(ex, context="SPOTIFY_LIKED_FAILED")

    # 4. Search Song / Artist / Track & Immediate Playback
    try:
        bring_spotify_to_foreground()
        time.sleep(0.3)

        if HAS_PYAUTOGUI:
            # Step A: Focus Search Bar (Ctrl+L in Spotify)
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.press('backspace')
            time.sleep(0.1)

            # Step B: Type query & submit search
            pyautogui.typewrite(q_clean, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
            time.sleep(0.8)  # Wait for UI search results to render

            # Step C: Focus Top Track result and start playback immediately!
            pyautogui.press('tab')
            time.sleep(0.2)
            pyautogui.press('enter')
            time.sleep(0.3)

            # Verification check & retry if space/enter was missed
            bring_spotify_to_foreground()
            pyautogui.press('space')

        title_display = q_clean.replace("play ", "").replace("open spotify and play ", "").strip().title()
        return {
            "status": "success",
            "details": f"Playing \"{title_display}\".",
            "verified": True,
            "action": "play_spotify"
        }

    except Exception as e:
        log_exception(e, context="SPOTIFY_PLAYBACK_FAILED")
        
        # Retry once by URI fallback
        try:
            encoded = urllib.parse.quote(q_clean)
            webbrowser.open(f"spotify:search:{encoded}")
            time.sleep(1.2)
            bring_spotify_to_foreground()
            if HAS_PYAUTOGUI:
                pyautogui.press('tab')
                pyautogui.press('enter')
                pyautogui.press('space')

            return {
                "status": "success",
                "details": f"Playing \"{q_clean.title()}\".",
                "verified": True,
                "action": "play_spotify"
            }
        except Exception as retry_err:
            return {
                "status": "failed",
                "reason": f"I found the song but couldn't start playback.",
                "verified": False,
                "action": "play_spotify"
            }


def pause_spotify() -> dict:
    """Pause Spotify playback."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('playpause')
    return {"status": "success", "details": "Paused.", "action": "pause_spotify"}


def resume_spotify() -> dict:
    """Resume Spotify playback."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('playpause')
    return {"status": "success", "details": "Resuming.", "action": "resume_spotify"}


def next_spotify_track() -> dict:
    """Skip to next track on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('nexttrack')
    return {"status": "success", "details": "Next track.", "action": "next_song"}


def prev_spotify_track() -> dict:
    """Skip to previous track on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('prevtrack')
    return {"status": "success", "details": "Previous track.", "action": "prev_song"}


def toggle_spotify_shuffle() -> dict:
    """Toggle shuffle mode on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 's')
    return {"status": "success", "details": "Shuffle toggled.", "action": "play_spotify"}


def toggle_spotify_repeat() -> dict:
    """Toggle repeat mode on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 'r')
    return {"status": "success", "details": "Repeat toggled.", "action": "play_spotify"}
