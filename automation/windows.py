"""
IRIS AI - Independent Windows System & Window Control Automation Engine
Handles app launching, app termination, system info telemetry, and window snapping.
"""

import os
import psutil
import platform
from rich.console import Console
from app_discovery import find_app_path
from window_manager import window_manager
from debug_logger import debug_log, log_exception

console = Console()


def open_system_app(target: str) -> dict:
    """Launch application by target name or keyword."""
    app_lower = target.lower().strip()
    debug_log(f"Opening application: '{app_lower}'", category="WINDOWS")

    app_path, matched_name = find_app_path(app_lower)
    if app_path and isinstance(app_path, str) and os.path.exists(app_path):
        try:
            os.startfile(app_path)
            return {
                "status": "success",
                "details": f"Launched {matched_name or target} ({app_path})",
                "action": "open_app"
            }
        except Exception as ex:
            log_exception(ex, context="OPEN_APP_FAILED")

    # Fallback to system command start
    try:
        os.system(f'start "" "{app_lower}"')
        return {
            "status": "success",
            "details": f"Triggered system start for '{target}'.",
            "action": "open_app"
        }
    except Exception as ex:
        return {
            "status": "failed",
            "reason": f"Could not launch '{target}': {ex}",
            "action": "open_app"
        }


def close_system_app(target: str) -> dict:
    """Terminate running application processes matching target name."""
    app_lower = target.lower().strip()
    closed = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pname = (proc.info['name'] or "").lower()
            if app_lower in pname:
                proc.terminate()
                closed += 1
        except Exception:
            pass

    if closed > 0:
        return {
            "status": "success",
            "details": f"Closed {closed} instance(s) of '{target}'.",
            "action": "close_app"
        }
    else:
        return {
            "status": "failed",
            "reason": f"No running processes found for '{target}'.",
            "action": "close_app"
        }


def get_system_telemetry() -> dict:
    """Return CPU, RAM, OS, and uptime telemetry."""
    cpu_pct = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory()
    boot_time = psutil.boot_time()
    uptime_sec = int(platform.time.time() - boot_time) if hasattr(platform, "time") else 0

    return {
        "status": "success",
        "cpu_percent": cpu_pct,
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "os": platform.system(),
        "release": platform.release(),
        "action": "get_system_info"
    }
