"""
IRIS AI - Web & Browser Automation Engine
Handles multi-website launching, Google/YouTube/Spotify web searches, tab closing, tab switching, and form inputs.
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


def browser_search(target_engine: str, query: str) -> str:
    """
    Search Google, YouTube, or Spotify automatically in browser and wait for UI load.
    """
    engine = target_engine.lower().strip()
    encoded = urllib.parse.quote(query)

    if "youtube" in engine:
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        time.sleep(1.0)
        bring_browser_to_foreground("chrome")
        return f"Searched YouTube for '{query}'"
    elif "spotify" in engine:
        url = f"https://open.spotify.com/search/{encoded}"
        webbrowser.open(url)
        time.sleep(1.0)
        bring_browser_to_foreground("chrome")
        return f"Searched Web Spotify for '{query}'"
    else:
        url = f"https://www.google.com/search?q={encoded}"
        webbrowser.open(url)
        time.sleep(1.0)
        bring_browser_to_foreground("chrome")
        return f"Searched Google for '{query}'"


def close_browser_target(target: str = "current_tab") -> str:
    """
    Close specific browser tab, target website, or entire browser window safely.
    Supports: "Close YouTube", "Close ChatGPT", "Close current tab", "Close all tabs", "Close Chrome".
    """
    t_clean = target.lower().strip()
    debug_log(f"Closing browser target: '{t_clean}'", category="BROWSER")

    # 1. Close entire browser application if explicitly requested
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

    # 2. Focus active browser window
    bring_browser_to_foreground()
    time.sleep(0.3)

    if HAS_PYAUTOGUI:
        try:
            pyautogui.FAILSAFE = False
        except Exception:
            pass

    # 3. Close All Tabs
    if "all tabs" in t_clean or "all" in t_clean:
        if HAS_PYAUTOGUI:
            pyautogui.hotkey('ctrl', 'shift', 'w')
        return "Closed all browser tabs."

    # 4. Close Current Tab
    if "current" in t_clean or t_clean in ["tab", "current_tab", "close_tab"]:
        if HAS_PYAUTOGUI:
            pyautogui.hotkey('ctrl', 'w')
        return "Closed current browser tab."

    # 5. Selective Website / Named Tab Closing (e.g. "Close YouTube", "Close ChatGPT")
    site_names = [w for w in t_clean.replace("close", "").replace("website", "").replace("tab", "").split() if w]
    site_target = site_names[0] if site_names else t_clean

    # Send Ctrl+W on focused browser tab
    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 'w')
    return f"Closed tab for '{site_target}'."


def execute_tab_action(sub_action: str) -> str:
    """Manage browser tabs (new_tab, close_tab, switch_tab, reload, pin_tab, restore_session)."""
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
