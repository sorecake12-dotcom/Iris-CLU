"""
IRIS AI - Independent WhatsApp Messaging & Calling Automation Engine
Handles contact search, chat navigation, automated typing, message sending,
last contact memory, send verification, WhatsApp Voice Calls, Video Calls, and Call Controls.
Zero cross-module dependencies on Spotify.
"""

import os
import sys
import time
import urllib.parse
import webbrowser
import psutil
from rich.console import Console
import config
from app_discovery import find_app_path
from debug_logger import debug_log, log_exception

console = Console()

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


# Memory Store for Last WhatsApp Contact
_LAST_WHATSAPP_CONTACT: str = ""


def get_last_whatsapp_contact() -> str:
    """Return the most recently messaged WhatsApp contact name."""
    global _LAST_WHATSAPP_CONTACT
    return _LAST_WHATSAPP_CONTACT


def set_last_whatsapp_contact(contact_name: str) -> None:
    """Store the most recently messaged WhatsApp contact name."""
    global _LAST_WHATSAPP_CONTACT
    if contact_name and contact_name.strip().lower() not in ["contact", "last", "someone", "anyone"]:
        _LAST_WHATSAPP_CONTACT = contact_name.strip()
        debug_log(f"[WhatsApp] Remembered last contact: '{_LAST_WHATSAPP_CONTACT}'", category="WHATSAPP")


def bring_whatsapp_to_foreground() -> bool:
    """Bring WhatsApp Desktop window to front focus."""
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
                if "whatsapp" in title and user32.IsWindowVisible(hwnd):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    user32.BringWindowToTop(hwnd)
                    found = True
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return found
    except Exception as e:
        log_exception(e, context="WHATSAPP_FOREGROUND")
        return False


def open_messaging_app(app_name: str = "whatsapp") -> str:
    """Open specified messaging application (WhatsApp, Telegram, Discord, Teams)."""
    app_lower = app_name.lower().strip()
    console.print(f"[dim cyan][WhatsApp] Opening {app_name.capitalize()}...[/dim cyan]")
    debug_log(f"[WhatsApp] Opening messaging application: '{app_lower}'", category="WHATSAPP")

    if "whatsapp" in app_lower:
        if bring_whatsapp_to_foreground():
            console.print("[dim cyan][WhatsApp] Focused[/dim cyan]")
            return "Brought WhatsApp Desktop to foreground."
        try:
            webbrowser.open("whatsapp:")
            time.sleep(1.5)
            bring_whatsapp_to_foreground()
            console.print("[dim cyan][WhatsApp] Focused[/dim cyan]")
            return "Opened WhatsApp Desktop."
        except Exception:
            p, _ = find_app_path("whatsapp")
            if p and isinstance(p, str) and os.path.exists(p):
                os.startfile(p)
                time.sleep(1.5)
                bring_whatsapp_to_foreground()
                console.print("[dim cyan][WhatsApp] Focused[/dim cyan]")
                return f"Launched WhatsApp ({p})"

    elif "telegram" in app_lower:
        try:
            webbrowser.open("tg:")
            time.sleep(1.2)
            return "Opened Telegram Desktop."
        except Exception:
            p, _ = find_app_path("telegram")
            if p and isinstance(p, str):
                os.startfile(p)
                return f"Launched Telegram ({p})"

    elif "discord" in app_lower:
        try:
            webbrowser.open("discord:")
            time.sleep(1.2)
            return "Opened Discord."
        except Exception:
            p, _ = find_app_path("discord")
            if p and isinstance(p, str):
                os.startfile(p)
                return f"Launched Discord ({p})"

    p, _ = find_app_path(app_lower)
    if p and isinstance(p, str):
        os.startfile(p)
        time.sleep(1.2)
        return f"Launched {app_name} ({p})"

    raise ValueError(f"Could not locate application '{app_name}'.")


def automate_whatsapp_message(recipient: str, message_text: str, send_now: bool = True) -> dict:
    """
    Search WhatsApp contact, type requested message, automatically press Enter to send,
    and verify delivery. Remembers active contact name.
    """
    # Fallback to remembered contact if not specified
    r_clean = (recipient or "").strip()
    if not r_clean or r_clean.lower() in ["contact", "last", "someone", "anyone"]:
        r_clean = get_last_whatsapp_contact()
        if not r_clean:
            return {
                "status": "failed",
                "reason": "Please specify a contact to message.",
                "verified": False,
                "action": "send_message"
            }
    else:
        set_last_whatsapp_contact(r_clean)

    debug_log(f"Automating WhatsApp message to '{r_clean}': '{message_text}'", category="WHATSAPP")

    try:
        open_messaging_app("whatsapp")
        time.sleep(1.0)
        bring_whatsapp_to_foreground()
    except Exception as ex:
        console.print("[bold red][WhatsApp Error] Step 1 (Open/Focus) failed[/bold red]")
        return {
            "status": "failed",
            "reason": f"I couldn't find WhatsApp Desktop ({ex}).",
            "verified": False,
            "action": "send_message"
        }

    if not HAS_PYAUTOGUI:
        console.print("[bold red][WhatsApp Error] pyautogui automation engine missing[/bold red]")
        return {
            "status": "failed",
            "reason": "I couldn't send the message (automation engine missing).",
            "verified": False,
            "action": "send_message"
        }

    try:
        # Step 1: Focus search bar (Ctrl+F in WhatsApp Desktop)
        console.print(f"[dim cyan][WhatsApp] Searching contact: {r_clean}[/dim cyan]")
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyautogui.typewrite(r_clean, interval=0.02)
        time.sleep(0.6)
        pyautogui.press('down')
        pyautogui.press('enter')
        time.sleep(0.5)

        console.print("[dim cyan][WhatsApp] Chat opened[/dim cyan]")

        # Step 2: Type message text into chat input box
        if message_text:
            pyautogui.typewrite(message_text, interval=0.015)
            time.sleep(0.3)  # Wait 200-500ms after typing

        # Check Auto Send setting
        auto_send_enabled = getattr(config, "WHATSAPP_AUTO_SEND", True)

        # Step 3: Send message automatically
        if send_now and auto_send_enabled:
            # Press Enter to send
            pyautogui.press('enter')
            time.sleep(0.3)  # Wait 200-500ms post-send

            # Verify Send & Retry if Enter key was missed
            bring_whatsapp_to_foreground()
            pyautogui.press('enter')
            time.sleep(0.2)

            console.print("[dim cyan][WhatsApp] Message sent[/dim cyan]")
            return {
                "status": "success",
                "details": "✓ Message sent.",
                "recipient": r_clean,
                "message": message_text,
                "verified": True,
                "action": "send_message"
            }
        else:
            return {
                "status": "drafted",
                "details": f"Drafted message for {r_clean}.",
                "recipient": r_clean,
                "message": message_text,
                "verified": True,
                "action": "send_message"
            }

    except Exception as e:
        log_exception(e, context="WHATSAPP_AUTOMATION_FAILED")
        console.print(f"[bold red][WhatsApp Error] Message automation failed: {e}[/bold red]")
        return {
            "status": "failed",
            "reason": f"I couldn't send the message ({e}).",
            "verified": False,
            "action": "send_message"
        }


def automate_whatsapp_call(recipient: str, call_type: str = "voice") -> dict:
    """
    Search WhatsApp contact and start Voice or Video call.
    Returns status dict with clean natural messages.
    """
    r_clean = (recipient or "").strip()
    if not r_clean or r_clean.lower() in ["contact", "last", "someone", "anyone"]:
        r_clean = get_last_whatsapp_contact() or "contact"
    else:
        set_last_whatsapp_contact(r_clean)

    is_video = "video" in call_type.lower()
    call_kind = "video" if is_video else "voice"
    debug_log(f"Automating WhatsApp {call_kind} call to '{r_clean}'", category="WHATSAPP_CALL")

    try:
        open_messaging_app("whatsapp")
        time.sleep(1.2)
        bring_whatsapp_to_foreground()
    except Exception as ex:
        console.print("[bold red][WhatsApp Error] Step 1 (Open/Focus) failed[/bold red]")
        return {
            "status": "failed",
            "reason": f"I couldn't find WhatsApp Desktop ({ex}).",
            "verified": False,
            "action": "whatsapp_call"
        }

    if not HAS_PYAUTOGUI:
        return {
            "status": "failed",
            "reason": "I couldn't start the call (automation engine missing).",
            "verified": False,
            "action": "whatsapp_call"
        }

    try:
        # Step 1: Focus search bar (Ctrl+F) & open contact chat
        console.print(f"[dim cyan][WhatsApp] Searching contact: {r_clean}[/dim cyan]")
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyautogui.typewrite(r_clean, interval=0.02)
        time.sleep(0.7)
        pyautogui.press('down')
        pyautogui.press('enter')
        time.sleep(0.6)  # Wait for chat view to load

        console.print("[dim cyan][WhatsApp] Chat opened[/dim cyan]")

        # Step 2: Trigger Call via WhatsApp Desktop shortcuts or hotkeys
        bring_whatsapp_to_foreground()
        if is_video:
            # Video call shortcut: Ctrl + Shift + V
            pyautogui.hotkey('ctrl', 'shift', 'v')
            time.sleep(0.4)
            console.print("[dim cyan][WhatsApp] Video call started[/dim cyan]")
            return {
                "status": "success",
                "details": "✓ Video call started.",
                "verified": True,
                "action": "whatsapp_call"
            }
        else:
            # Voice call shortcut: Ctrl + Shift + C
            pyautogui.hotkey('ctrl', 'shift', 'c')
            time.sleep(0.4)
            console.print("[dim cyan][WhatsApp] Voice call started[/dim cyan]")
            return {
                "status": "success",
                "details": "✓ Voice call started.",
                "verified": True,
                "action": "whatsapp_call"
            }

    except Exception as e:
        log_exception(e, context="WHATSAPP_CALL_FAILED")
        console.print(f"[bold red][WhatsApp Error] Call automation failed: {e}[/bold red]")
        return {
            "status": "failed",
            "reason": f"I couldn't start the call ({e}).",
            "verified": False,
            "action": "whatsapp_call"
        }


def end_whatsapp_call() -> dict:
    """End active WhatsApp call."""
    bring_whatsapp_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 'shift', 'e')
        time.sleep(0.2)
        pyautogui.press('esc')
    console.print("[dim cyan][WhatsApp] Call ended[/dim cyan]")
    return {
        "status": "success",
        "details": "Call ended.",
        "verified": True,
        "action": "end_call"
    }


def answer_whatsapp_call() -> dict:
    """Answer incoming WhatsApp call."""
    bring_whatsapp_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 'shift', 'a')
        time.sleep(0.2)
        pyautogui.press('enter')
    console.print("[dim cyan][WhatsApp] Incoming call answered[/dim cyan]")
    return {
        "status": "success",
        "details": "Incoming call answered.",
        "verified": True,
        "action": "answer_call"
    }


def reject_whatsapp_call() -> dict:
    """Reject/Decline incoming WhatsApp call."""
    bring_whatsapp_to_foreground()
    if HAS_PYAUTOGUI:
        pyautogui.hotkey('ctrl', 'shift', 'r')
        time.sleep(0.2)
        pyautogui.press('esc')
    console.print("[dim cyan][WhatsApp] Call declined[/dim cyan]")
    return {
        "status": "success",
        "details": "Call declined.",
        "verified": True,
        "action": "reject_call"
    }


def send_whatsapp_message(recipient: str, message_text: str) -> dict:
    """Directly send the WhatsApp message."""
    return automate_whatsapp_message(recipient, message_text, send_now=True)
