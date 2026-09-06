"""
IRIS AI - Independent Browser Automation Engine
Handles multi-provider web search (Google, YouTube, Spotify, Bing, GitHub, Stack Overflow),
URL opening, tab management, and session restoration.
"""

import os
import time
import urllib.parse
import webbrowser
import psutil
from rich.console import Console
from debug_logger import debug_log, log_exception

console = Console()

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


def bring_browser_to_foreground(browser_name: str = "chrome") -> bool:
    """Bring target browser window to front focus on Windows."""
    try:
        import ctypes
        user32 = ctypes.windll.user32

        b_lower = browser_name.lower().strip()

        def enum_windows_callback(hwnd, extra):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()
                if any(w in title for w in [b_lower, "chrome", "edge", "firefox", "browser"]) and user32.IsWindowVisible(hwnd):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return True
    except Exception as e:
        log_exception(e, context="BROWSER_FOREGROUND")
        return False


def open_multiple_websites(urls: list[str]) -> str:
    """Open multiple websites from a single command list and wait for pages to load."""
    opened = []
    for u in urls:
        u_clean = u.strip()
        if not u_clean:
            continue
        if not u_clean.startswith("http://") and not u_clean.startswith("https://"):
            u_clean = "https://" + u_clean
        webbrowser.open(u_clean)
        opened.append(u_clean)
        time.sleep(0.5)

    bring_browser_to_foreground()
    return f"Opened {len(opened)} website(s): {', '.join(opened)}"


def parse_browser_search_query(user_input: str) -> tuple[str, str] | None:
    """
    Parse user query for browser search provider and search term.
    Returns (engine, search_term) if matched, or None.

    Supported Examples:
      - "Search Google for Python" -> ("google", "Python")
      - "Open YouTube and search Barsaat song" -> ("youtube", "Barsaat song")
      - "Search Spotify for Believer" -> ("spotify", "Believer")
      - "Search GitHub for Iris AI" -> ("github", "Iris AI")
      - "Search Stack Overflow for pyautogui" -> ("stackoverflow", "pyautogui")
      - "Search Bing for Windows 11" -> ("bing", "Windows 11")
    """
    text = user_input.strip()
    t_lower = text.lower()

    providers = {
        "google": ["google", "on google", "for google"],
        "youtube": ["youtube", "on youtube", "for youtube"],
        "spotify": ["spotify", "on spotify", "for spotify"],
        "github": ["github", "on github", "for github"],
        "stackoverflow": ["stackoverflow", "stack overflow", "on stack overflow", "for stack overflow"],
        "bing": ["bing", "on bing", "for bing"],
    }

    for prov_name, keywords in providers.items():
        for kw in keywords:
            # Pattern A: "search <kw> for <term>"
            prefix_a = f"search {kw} for "
            if t_lower.startswith(prefix_a):
                term = text[len(prefix_a):].strip()
                if term:
                    return (prov_name, term)

            # Pattern B: "open <kw> and search <term>"
            prefix_b = f"open {kw} and search "
            if t_lower.startswith(prefix_b):
                term = text[len(prefix_b):].strip()
                if term:
                    return (prov_name, term)

            # Pattern C: "<kw> search <term>"
            prefix_c = f"{kw} search "
            if t_lower.startswith(prefix_c):
                term = text[len(prefix_c):].strip()
                if term:
                    return (prov_name, term)

            # Pattern D: "search for <term> on/for <kw>" or "search <term> on/for <kw>"
            for prep in [" on ", " for "]:
                suffix = f"{prep}{kw}"
                if t_lower.endswith(suffix) and any(t_lower.startswith(p) for p in ["search for ", "search ", "find ", "look up "]):
                    for p in ["search for ", "search ", "find ", "look up "]:
                        if t_lower.startswith(p):
                            term = text[len(p):-len(suffix)].strip()
                            if term:
                                return (prov_name, term)

    # General fallback: "browser search <term>"
    if t_lower.startswith("browser search "):
        term = text[len("browser search "):].strip()
        if term:
            return ("google", term)

    return None


def browser_search(target_engine: str, query: str) -> dict | str:
    """
    Search Google, YouTube, Spotify, Bing, GitHub, or Stack Overflow in default browser.
    Encodes query string using quote_plus for '+' space encoding.
    """
    engine = target_engine.lower().strip()
    q_clean = query.strip()
    encoded = urllib.parse.quote_plus(q_clean)
    debug_log(f"Executing browser search on '{engine}' for query '{q_clean}' ({encoded})", category="BROWSER")

    # Provider 1: Spotify
    if "spotify" in engine:
        from automation.spotify import is_spotify_running, play_spotify
        if is_spotify_running():
            res = play_spotify(q_clean)
            return {
                "status": "success",
                "details": f"Playing \"{q_clean}\" on Spotify Desktop, Boss.",
                "action": "browser_search"
            }
        else:
            url = f"https://open.spotify.com/search/{encoded}"
            webbrowser.open(url)
            time.sleep(0.4)
            bring_browser_to_foreground()
            return {
                "status": "success",
                "details": f"Searching Spotify for \"{q_clean}\", Boss.",
                "action": "browser_search"
            }

    # Provider 2: YouTube
    elif "youtube" in engine:
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        time.sleep(0.4)
        bring_browser_to_foreground()
        return {
            "status": "success",
            "details": f"Searching YouTube for \"{q_clean}\", Boss.",
            "action": "browser_search"
        }

    # Provider 3: GitHub
    elif "github" in engine:
        url = f"https://github.com/search?q={encoded}"
        webbrowser.open(url)
        time.sleep(0.4)
        bring_browser_to_foreground()
        return {
            "status": "success",
            "details": f"Searching GitHub for \"{q_clean}\", Boss.",
            "action": "browser_search"
        }

    # Provider 4: Stack Overflow
    elif "stackoverflow" in engine or "stack overflow" in engine:
        url = f"https://stackoverflow.com/search?q={encoded}"
        webbrowser.open(url)
        time.sleep(0.4)
        bring_browser_to_foreground()
        return {
            "status": "success",
            "details": f"Searching Stack Overflow for \"{q_clean}\", Boss.",
            "action": "browser_search"
        }

    # Provider 5: Bing
    elif "bing" in engine:
        url = f"https://www.bing.com/search?q={encoded}"
        webbrowser.open(url)
        time.sleep(0.4)
        bring_browser_to_foreground()
        return {
            "status": "success",
            "details": f"Searching Bing for \"{q_clean}\", Boss.",
            "action": "browser_search"
        }

    # Provider 6: Google (default)
    else:
        url = f"https://www.google.com/search?q={encoded}"
        webbrowser.open(url)
        time.sleep(0.4)
        bring_browser_to_foreground()
        return {
            "status": "success",
            "details": f"Searching Google for \"{q_clean}\", Boss.",
            "action": "browser_search"
        }


def close_browser_target(target: str = "current_tab") -> str:
    """
    Close specific browser tab, target website, or entire browser window safely.
    """
    t_clean = target.lower().strip()
    debug_log(f"Closing browser target: '{t_clean}'", category="BROWSER")

    if any(w in t_clean for w in ["close chrome", "close browser", "close edge", "close firefox"]):
        proc_name = "chrome" if "chrome" in t_clean else ("msedge" if "edge" in t_clean else "firefox")
        closed_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc_name in proc.info['name'].lower():
                    proc.terminate()
                    closed_count += 1
            except Exception:
                pass
        if closed_count > 0:
            return f"Closed {proc_name.capitalize()} browser application."
        else:
            return f"No running process found for {proc_name.capitalize()}."

    bring_browser_to_foreground()
    time.sleep(0.3)

    if HAS_PYAUTOGUI:
        try:
            pyautogui.FAILSAFE = False
        except Exception:
            pass

    if "all tabs" in t_clean or "all" in t_clean:
        if HAS_PYAUTOGUI:
            pyautogui.hotkey('ctrl', 'shift', 'w')
        return "Closed all browser tabs."

    if "current" in t_clean or t_clean in ["tab", "current_tab", "close_tab"]:
        if HAS_PYAUTOGUI:
            pyautogui.hotkey('ctrl', 'w')
        return "Closed current browser tab."

    site_names = [w for w in t_clean.replace("close", "").replace("website", "").replace("tab", "").split() if w]
    site_target = site_names[0] if site_names else t_clean

    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 'w')
    return f"Closed tab for '{site_target}'."


def execute_tab_action(sub_action: str) -> str:
    """Manage browser tabs (new_tab, close_tab, switch_tab, reload, restore_session)."""
    act = sub_action.lower().strip()
    bring_browser_to_foreground()
    time.sleep(0.3)

    if HAS_PYAUTOGUI:
        if act in ["new_tab", "new"]:
            pyautogui.hotkey('ctrl', 't')
            return "Opened new browser tab."
        elif act in ["close_tab", "close"]:
            pyautogui.hotkey('ctrl', 'w')
            return "Closed active browser tab."
        elif act in ["switch_tab", "switch", "next_tab"]:
            pyautogui.hotkey('ctrl', 'tab')
            return "Switched to next browser tab."
        elif act in ["reload", "refresh"]:
            pyautogui.hotkey('ctrl', 'r')
            return "Reloaded active page."
        elif act in ["restore_session", "restore_tab", "reopen", "undo_close"]:
            pyautogui.hotkey('ctrl', 'shift', 't')
            return "Restored closed browser tab / session."

    return f"Browser tab action '{act}' executed."


def restore_browser_session() -> str:
    """Restore recently closed browser tab or previous session."""
    bring_browser_to_foreground()
    time.sleep(0.3)
    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 'shift', 't')
        return "Restored closed browser tab / session (Ctrl+Shift+T)."
    return "Browser session restore requested."


def fill_form_text(selector_or_text: str) -> str:
    """Simulate typing text into active web search input or form field."""
    bring_browser_to_foreground()
    time.sleep(0.3)
    if HAS_PYAUTOGUI and selector_or_text:
        pyautogui.typewrite(selector_or_text, interval=0.02)
        time.sleep(0.2)
        pyautogui.press('enter')
        return f"Typed text into active input field ({len(selector_or_text)} chars)."
    return "Form typing simulated."
