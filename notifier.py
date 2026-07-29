"""
IRIS AI - Windows Toast Notification System
Displays Windows desktop toast notifications for timer completions and reminders.
Uses win10toast if available, falls back to PowerShell New-BurntToastNotification
or a simple PowerShell MessageBox — always works with zero binary dependencies.
"""

import os
import subprocess
import threading
from debug_logger import debug_log, log_exception

# ── Try win10toast (optional fast path) ──────────────────────────
try:
    from win10toast import ToastNotifier
    _toaster = ToastNotifier()
    HAS_WIN10TOAST = True
except ImportError:
    _toaster = None
    HAS_WIN10TOAST = False


# ── Core toast function ───────────────────────────────────────────

def _powershell_toast(title: str, message: str):
    """
    Fallback: show a Windows toast notification using PowerShell.
    Works on Windows 10/11 with no extra Python packages.
    Uses BurntToast if installed, otherwise falls back to a balloon tip via
    Windows Script Host.
    """
    # Escape single quotes
    safe_title   = title.replace("'", "`'")
    safe_message = message.replace("'", "`'")

    # Try BurntToast (common on modern Windows)
    burnt_toast_cmd = (
        f"$m = Get-Module -Name BurntToast -ListAvailable; "
        f"if ($m) {{ "
        f"  Import-Module BurntToast; "
        f"  New-BurntToastNotification -Text '{safe_title}', '{safe_message}' "
        f"}} else {{ "
        # Fallback: System.Windows.Forms balloon tip
        f"  [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
        f"  $notify = New-Object System.Windows.Forms.NotifyIcon; "
        f"  $notify.Icon = [System.Drawing.SystemIcons]::Information; "
        f"  $notify.BalloonTipIcon = 'Info'; "
        f"  $notify.BalloonTipTitle = '{safe_title}'; "
        f"  $notify.BalloonTipText = '{safe_message}'; "
        f"  $notify.Visible = $True; "
        f"  $notify.ShowBalloonTip(5000); "
        f"  Start-Sleep -Milliseconds 5500; "
        f"  $notify.Dispose() "
        f"}}"
    )

    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", burnt_toast_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
    except Exception as ex:
        log_exception(ex, context="NOTIFIER_POWERSHELL")


def send_toast(title: str, message: str, duration: int = 5):
    """
    Show a Windows desktop toast notification in a background thread.
    Non-blocking — returns immediately.

    Args:
        title:    Notification title line.
        message:  Notification body text.
        duration: How long to show it (seconds). Only honoured by win10toast.
    """
    def _fire():
        try:
            if HAS_WIN10TOAST and _toaster:
                _toaster.show_toast(
                    title,
                    message,
                    duration=duration,
                    threaded=False,
                    icon_path=None
                )
            else:
                _powershell_toast(title, message)
            debug_log(f"Toast sent: {title} — {message}", category="NOTIFIER")
        except Exception as ex:
            log_exception(ex, context="NOTIFIER_FIRE")

    t = threading.Thread(target=_fire, daemon=True)
    t.start()


# ── Convenience wrappers ──────────────────────────────────────────

def notify_timer_done(label: str = "Timer"):
    """Called by TaskScheduler when a timer finishes."""
    send_toast(
        title="⏱ IRIS AI — Timer Done",
        message=f"Boss, your {label} has finished!",
        duration=6
    )

def notify_reminder(message: str):
    """Called by TaskScheduler for recurring reminders."""
    send_toast(
        title="🔔 IRIS AI — Reminder",
        message=message,
        duration=6
    )

def notify_action_done(description: str):
    """Called when a delayed automation action fires."""
    send_toast(
        title="⚡ IRIS AI — Action Complete",
        message=description,
        duration=5
    )
