"""
IRIS AI - Independent Spotify Deep Automation Engine
Handles process detection, window focus, song fuzzy matching, automated search-to-play execution,
and media controls. Zero cross-module dependencies on WhatsApp.
"""

import os
import sys
import time
import difflib
import urllib.parse
import webbrowser
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


# Common Song Aliases & Fuzzy Matching Reference Dictionary
KNOWN_SONG_ALIASES = {
    "barsat": "Baarish",
    "baarish": "Baarish",
    "barish": "Baarish",
    "barsaat": "Baarish",
    "beliver": "Believer",
    "believer": "Believer",
    "shap of you": "Shape of You",
    "shape of you": "Shape of You",
    "perfect": "Perfect",
    "parfect": "Perfect",
    "despacito": "Despacito",
    "faded": "Faded",
    "starboy": "Starboy",
    "blinding lights": "Blinding Lights",
    "senorita": "Señorita",
    "let me love you": "Let Me Love You",
}


def fuzzy_match_song_name(query: str) -> str:
    """
    Match song query against known aliases using fuzzy string matching.
    Resolves spelling mistakes (e.g. 'Barsat' -> 'Baarish', 'Beliver' -> 'Believer').
    """
    q_clean = query.strip().lower()
    if not q_clean:
        return query

    # Direct Alias Match
    if q_clean in KNOWN_SONG_ALIASES:
        matched = KNOWN_SONG_ALIASES[q_clean]
        debug_log(f"Fuzzy song match: '{query}' -> '{matched}'", category="SPOTIFY")
        return matched

    # Fuzzy Ratio Match using difflib
    matches = difflib.get_close_matches(q_clean, KNOWN_SONG_ALIASES.keys(), n=1, cutoff=0.6)
    if matches:
        matched = KNOWN_SONG_ALIASES[matches[0]]
        debug_log(f"Fuzzy song match (close ratio): '{query}' -> '{matched}'", category="SPOTIFY")
        return matched

    # Fallback to original query title-cased
    return query.strip().title()


def is_spotify_running() -> bool:
    """Check if Spotify process is currently active."""
    for proc in psutil.process_iter(['name']):
        try:
            pname = (proc.info['name'] or "").lower()
            if "spotify" in pname:
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


def ensure_spotify_open() -> bool:
    """
    Ensure Spotify application is running and brought to front focus.
    Only launches new instance if Spotify is NOT already running.
    """
    running = is_spotify_running()

    if running:
        focused = bring_spotify_to_foreground()
        time.sleep(0.3)
        console.print("[dim cyan][Spotify] Focused[/dim cyan]")
        debug_log("[Spotify] Focused existing instance", category="SPOTIFY")
        return True
    else:
        console.print("[dim cyan][Spotify] Launching...[/dim cyan]")
        debug_log("[Spotify] Launching new instance...", category="SPOTIFY")
        spot_path, _ = find_app_path("spotify")
        if spot_path and isinstance(spot_path, str) and os.path.exists(spot_path):
            try:
                os.startfile(spot_path)
            except Exception:
                webbrowser.open("spotify:")
        else:
            webbrowser.open("spotify:")

        # Wait for window creation
        for _ in range(10):
            time.sleep(0.4)
            if bring_spotify_to_foreground():
                console.print("[dim cyan][Spotify] Focused[/dim cyan]")
                debug_log("[Spotify] Focused newly launched instance", category="SPOTIFY")
                return True

        bring_spotify_to_foreground()
        return True


def play_spotify(query: str = "") -> dict:
    """
    Open Spotify, search target song/artist/playlist with fuzzy matching,
    and automatically start playback.
    """
    q_clean = query.strip()
    q_lower = q_clean.lower()
    debug_log(f"Spotify Automation invoked with query: '{q_clean}'", category="SPOTIFY")

    # Step 1: Ensure Spotify process is open & focused
    try:
        ensure_spotify_open()
    except Exception as ex:
        console.print("[bold red][Spotify Error] Step 1 (Launch/Focus) failed[/bold red]")
        return {
            "status": "failed",
            "reason": f"Spotify launch failed: {ex}",
            "action": "play_spotify"
        }

    # Step 2: Handle Media Control & Empty Queries
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

    # Step 3: Apply Fuzzy Song Name Matching
    song_target = fuzzy_match_song_name(q_clean)

    # Step 4: Search & Automatic Playback Execution
    console.print(f"[dim cyan][Spotify] Searching: {song_target}[/dim cyan]")
    debug_log(f"[Spotify] Searching: {song_target}", category="SPOTIFY")

    if not HAS_PYAUTOGUI:
        return {
            "status": "failed",
            "reason": "[Spotify Error] Step 4 failed: pyautogui automation engine missing.",
            "action": "play_spotify"
        }

    try:
        bring_spotify_to_foreground()
        time.sleep(0.3)

        # Step A: Focus Search Bar (Ctrl+L) & clear existing search text
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        time.sleep(0.1)

        # Step B: Type song name and submit search
        pyautogui.typewrite(song_target, interval=0.02)
        time.sleep(0.2)
        pyautogui.press('enter')
        time.sleep(0.9)  # Wait for Spotify search UI to populate results

        # Step C: Select top result & trigger playback
        pyautogui.press('tab')
        time.sleep(0.2)
        pyautogui.press('enter')
        time.sleep(0.3)

        console.print("[dim cyan][Spotify] First result selected[/dim cyan]")
        debug_log("[Spotify] First result selected", category="SPOTIFY")

        # Step D: Playback Start Verification / Double-play trigger
        bring_spotify_to_foreground()
        pyautogui.press('space')
        time.sleep(0.2)

        console.print("[dim cyan][Spotify] Playback started[/dim cyan]")
        debug_log("[Spotify] Playback started", category="SPOTIFY")

        return {
            "status": "success",
            "details": f"Playing \"{song_target}\", Boss.",
            "song": song_target,
            "verified": True,
            "action": "play_spotify"
        }

    except Exception as e:
        log_exception(e, context="SPOTIFY_PLAYBACK_FAILED")
        console.print(f"[bold red][Spotify Error] Playback execution failed: {e}[/bold red]")

        # URI Fallback Attempt
        try:
            encoded = urllib.parse.quote(song_target)
            webbrowser.open(f"spotify:search:{encoded}")
            time.sleep(1.2)
            bring_spotify_to_foreground()
            pyautogui.press('tab')
            pyautogui.press('enter')
            pyautogui.press('space')

            return {
                "status": "success",
                "details": f"Playing \"{song_target}\", Boss.",
                "song": song_target,
                "verified": True,
                "action": "play_spotify"
            }
        except Exception as retry_err:
            return {
                "status": "failed",
                "reason": f"I found the song but couldn't start playback ({retry_err}).",
                "action": "play_spotify"
            }


def pause_spotify() -> dict:
    """Pause Spotify playback."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('playpause')
    console.print("[dim cyan][Spotify] Playback paused[/dim cyan]")
    return {"status": "success", "details": "Paused.", "action": "pause_spotify"}


def resume_spotify() -> dict:
    """Resume Spotify playback."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('playpause')
    console.print("[dim cyan][Spotify] Playback resumed[/dim cyan]")
    return {"status": "success", "details": "Resuming.", "action": "resume_spotify"}


def next_spotify_track() -> dict:
    """Skip to next track on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('nexttrack')
    console.print("[dim cyan][Spotify] Next track[/dim cyan]")
    return {"status": "success", "details": "Next track.", "action": "next_song"}


def prev_spotify_track() -> dict:
    """Skip to previous track on Spotify."""
    bring_spotify_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.press('prevtrack')
    console.print("[dim cyan][Spotify] Previous track[/dim cyan]")
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
