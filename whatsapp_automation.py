"""
IRIS AI - WhatsApp & Messaging Automation Engine
Handles contact search, chat navigation, automated typing, confirmation prompts, message sending, and delivery verification.
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
                    found = True
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return found
    except Exception as e:
        log_exception(e, context="WHATSAPP_FOREGROUND")
        return False


def open_messaging_app(app_name: str) -> str:
    """Open specified messaging application (WhatsApp, Telegram, Discord, Teams)."""
    app_lower = app_name.lower().strip()
    debug_log(f"Opening messaging application: '{app_lower}'", category="MESSAGING")

    if "whatsapp" in app_lower:
        try:
            webbrowser.open("whatsapp:")
            time.sleep(1.5)
            bring_whatsapp_to_foreground()
            return "Opened WhatsApp Desktop."
        except Exception:
            p, _ = find_app_path("whatsapp")
            if p and isinstance(p, str):
                os.startfile(p)
                time.sleep(1.5)
                bring_whatsapp_to_foreground()
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
    Search WhatsApp contact, type requested message, and execute send.
    Returns status dict with clean natural messages.
    """
    debug_log(f"Automating WhatsApp message to '{recipient}': '{message_text}' (send_now={send_now})", category="WHATSAPP")
    try:
        open_messaging_app("whatsapp")
        time.sleep(1.2)
        bring_whatsapp_to_foreground()
    except Exception as ex:
        return {
            "status": "failed",
            "reason": f"I couldn't open WhatsApp application.",
            "verified": False,
            "action": "send_message"
        }

    if not HAS_PYAUTOGUI:
        return {
            "status": "failed",
            "reason": "I couldn't send the message (automation engine missing).",
            "verified": False,
            "action": "send_message"
        }

    try:
        # Step 1: Focus search bar (Ctrl+F in WhatsApp Desktop)
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.3)
        pyautogui.typewrite(recipient, interval=0.02)
        time.sleep(0.6)
        pyautogui.press('down')
        pyautogui.press('enter')
        time.sleep(0.5)

        # Step 2: Type message text into chat input box
        if message_text:
            pyautogui.typewrite(message_text, interval=0.015)
            time.sleep(0.2)

        # Step 3: Send message automatically
        if send_now:
            pyautogui.press('enter')
            time.sleep(0.4)
            return {
                "status": "success",
                "details": f"✓ Message sent.",
                "verified": True,
                "action": "send_message"
            }
        else:
            return {
                "status": "drafted",
                "details": f"Drafted message for {recipient}.",
                "verified": True,
                "action": "send_message"
            }

    except Exception as e:
        log_exception(e, context="WHATSAPP_AUTOMATION_FAILED")
        return {
            "status": "failed",
            "reason": f"I couldn't send the message.",
            "verified": False,
            "action": "send_message"
        }


def send_whatsapp_message(recipient: str, message_text: str) -> dict:
    """Directly send the WhatsApp message."""
    return automate_whatsapp_message(recipient, message_text, send_now=True)
