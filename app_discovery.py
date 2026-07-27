"""
IRIS AI - Robust Application Discovery & Launch Engine
Redesigned Application Discovery Service supporting multi-tiered search,
shortcut resolution, registry indexing, window foregrounding for running apps,
app caching, process verification, and multi-match disambiguation.
"""

import os
import sys
import re
import json
import time
import shutil
import glob
import ctypes
import winreg
import psutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Union

import config
from debug_logger import debug_log, log_exception

# Built-in Windows Application Mapping
BUILTIN_APPS: Dict[str, dict] = {
    "explorer": {
        "name": "File Explorer",
        "aliases": ["explorer", "file explorer", "explorer.exe", "windows explorer", "my computer", "this pc"],
        "path": r"C:\Windows\explorer.exe",
        "exec": "explorer.exe",
        "type": "executable"
    },
    "edge": {
        "name": "Microsoft Edge",
        "aliases": ["edge", "microsoft edge", "msedge", "msedge.exe", "browser"],
        "path": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "fallback_paths": [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\msedge.exe")
        ],
        "exec": "msedge.exe",
        "type": "executable"
    },
    "notepad": {
        "name": "Notepad",
        "aliases": ["notepad", "notepad.exe", "text editor"],
        "path": r"C:\Windows\notepad.exe",
        "exec": "notepad.exe",
        "type": "executable"
    },
    "calculator": {
        "name": "Calculator",
        "aliases": ["calc", "calculator", "calc.exe"],
        "path": r"C:\Windows\System32\calc.exe",
        "protocol": "ms-calculator:",
        "exec": "calc.exe",
        "type": "executable"
    },
    "paint": {
        "name": "Paint",
        "aliases": ["paint", "mspaint", "mspaint.exe"],
        "path": r"C:\Windows\System32\mspaint.exe",
        "exec": "mspaint.exe",
        "type": "executable"
    },
    "taskmanager": {
        "name": "Task Manager",
        "aliases": ["taskmgr", "task manager", "taskmgr.exe"],
        "path": r"C:\Windows\System32\taskmgr.exe",
        "exec": "taskmgr.exe",
        "type": "executable"
    },
    "controlpanel": {
        "name": "Control Panel",
        "aliases": ["control", "control panel", "control.exe"],
        "path": r"C:\Windows\System32\control.exe",
        "exec": "control.exe",
        "type": "executable"
    },
    "settings": {
        "name": "Windows Settings",
        "aliases": ["settings", "windows settings", "ms-settings"],
        "protocol": "ms-settings:",
        "exec": "SystemSettings.exe",
        "type": "protocol"
    },
    "cmd": {
        "name": "Command Prompt",
        "aliases": ["cmd", "command prompt", "cmd.exe"],
        "path": r"C:\Windows\System32\cmd.exe",
        "exec": "cmd.exe",
        "type": "executable"
    },
    "powershell": {
        "name": "PowerShell",
        "aliases": ["powershell", "powershell.exe", "windowspowershell"],
        "path": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "exec": "powershell.exe",
        "type": "executable"
    },
    "terminal": {
        "name": "Windows Terminal",
        "aliases": ["wt", "windows terminal", "wt.exe"],
        "path": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"),
        "exec": "WindowsTerminal.exe",
        "type": "executable"
    }
}

# Common App Aliases for Fast Resolution
APP_ALIASES: Dict[str, List[str]] = {
    "chrome": ["chrome.exe", "Google Chrome"],
    "google chrome": ["chrome.exe"],
    "firefox": ["firefox.exe", "Mozilla Firefox"],
    "vscode": ["code.exe", "Visual Studio Code", "Code"],
    "code": ["code.exe"],
    "vs code": ["code.exe"],
    "spotify": ["spotify.exe", "Spotify"],
    "whatsapp": ["whatsapp.exe", "WhatsApp"],
    "telegram": ["telegram.exe", "Telegram"],
    "discord": ["discord.exe", "Discord"],
    "teams": ["ms-teams.exe", "teams.exe", "Microsoft Teams"],
    "vlc": ["vlc.exe", "VLC media player"],
    "word": ["winword.exe", "Microsoft Word"],
    "excel": ["excel.exe", "Microsoft Excel"],
    "powerpoint": ["powerpnt.exe", "Microsoft PowerPoint"],
    "obs": ["obs64.exe", "obs32.exe", "obs.exe"],
    "steam": ["steam.exe", "Steam"],
    "epic": ["EpicGamesLauncher.exe"],
    "epic games": ["EpicGamesLauncher.exe"]
}


def normalize_query(query: str) -> str:
    """Sanitize and strip action verbs like 'open', 'launch', 'start', 'run', 'the'."""
    if not query:
        return ""
    q = query.lower().strip()
    q = re.sub(r"^(open|launch|start|run|show)\s+", "", q)
    q = re.sub(r"^the\s+", "", q)
    return q.strip()


def resolve_shortcut_target(lnk_path: str) -> str:
    """Resolves actual target executable path from a Windows .lnk shortcut file."""
    if not os.path.exists(lnk_path) or not lnk_path.lower().endswith(".lnk"):
        return lnk_path

    try:
        cmd = f'''powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}'); Write-Output $s.TargetPath"'''
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
        target = res.stdout.strip()
        if target and os.path.exists(target):
            return target
    except Exception:
        pass

    return lnk_path


def bring_window_to_foreground(process_name_or_exe: str) -> bool:
    """
    Detects if the application is already running and brings its top-level window to the foreground.
    Returns True if successfully brought to foreground, False otherwise.
    """
    if os.name != "nt":
        return False

    p_clean = os.path.basename(process_name_or_exe).lower().replace(".exe", "")

    matching_pids = set()
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            name = (proc.info['name'] or "").lower().replace(".exe", "")
            exe = (proc.info['exe'] or "").lower()
            if p_clean in name or (proc.info['exe'] and p_clean in os.path.basename(exe)):
                matching_pids.add(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not matching_pids:
        return False

    found_hwnd = []

    def enum_windows_callback(hwnd, extra):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in matching_pids:
                # Exclude toolbars / tiny windows
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    found_hwnd.append(hwnd)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

    if found_hwnd:
        target_hwnd = found_hwnd[0]
        # SW_RESTORE = 9
        ctypes.windll.user32.ShowWindow(target_hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(target_hwnd)
        ctypes.windll.user32.BringWindowToTop(target_hwnd)
        return True

    return False


class ApplicationDiscoveryService:
    """Comprehensive Multi-Tiered Application Discovery & Launch Service for IRIS AI."""

    def __init__(self):
        self.cache_file = Path.home() / ".iris_app_index.json"
        self.index_cache: Dict[str, List[Tuple[str, str]]] = {}
        self.load_cache()

    def _log_debug(self, stage: str, message: str):
        """Format debug logs according to spec: [APP] Stage: message."""
        if config.DEBUG_MODE:
            console = config.THEMES.get(config.DEFAULT_THEME)
            from rich.console import Console
            c = Console()
            c.print(f"[bold cyan][APP] {stage}[/bold cyan] [dim white]{message}[/dim white]")
        debug_log(f"{stage}: {message}", category="APP")

    def load_cache(self):
        """Load persistent application cache if available."""
        try:
            if self.cache_file.exists():
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.index_cache = data
        except Exception:
            self.index_cache = {}

    def save_cache(self):
        """Save application cache to disk."""
        try:
            self.cache_file.write_text(json.dumps(self.index_cache, indent=2), encoding="utf-8")
        except Exception:
            pass

    def search_all_tiers(self, query: str) -> List[Tuple[str, str]]:
        """
        Search for applications across 7 structured tiers in order:
        1. Built-in Windows Applications
        2. Windows App Execution Aliases
        3. Start Menu Shortcuts (User + System)
        4. Desktop Shortcuts (User + Public)
        5. Installed Programs & Registry (Uninstall + App Paths)
        6. PATH Executables
        7. Common Installation Folders
        """
        q_norm = normalize_query(query)
        if not q_norm:
            return []

        self._log_debug("Searching...", f"Query: '{query}' (Normalized: '{q_norm}')")

        # Fast Cache Check
        if q_norm in self.index_cache:
            cached_entries = self.index_cache[q_norm]
            # Validate cached paths still exist
            valid_cached = []
            for path_str, desc in cached_entries:
                if path_str.startswith("ms-") or os.path.exists(path_str):
                    valid_cached.append((path_str, desc))
            if valid_cached:
                self._log_debug("Match found", f"Cache hit for '{q_norm}' ({len(valid_cached)} item(s))")
                return valid_cached

        candidates: List[Tuple[str, str]] = []
        seen_paths: Set[str] = set()

        def add_candidate(path_val: str, desc: str):
            clean_p = path_val if path_val.startswith("ms-") else os.path.abspath(path_val)
            if clean_p not in seen_paths:
                seen_paths.add(clean_p)
                candidates.append((clean_p, desc))

        # ---------------------------------------------------------------------
        # TIER 1: Built-in Windows Applications
        # ---------------------------------------------------------------------
        for app_key, info in BUILTIN_APPS.items():
            if q_norm == app_key or any(alias == q_norm or alias in q_norm for alias in info["aliases"]):
                if info.get("protocol"):
                    add_candidate(info["protocol"], f"Built-in Windows Protocol '{info['name']}'")
                elif info.get("path") and os.path.exists(info["path"]):
                    add_candidate(info["path"], f"Built-in Windows App '{info['name']}'")
                elif info.get("fallback_paths"):
                    for fp in info["fallback_paths"]:
                        if os.path.exists(fp):
                            add_candidate(fp, f"Built-in Windows App '{info['name']}'")
                            break
                elif info.get("exec"):
                    w_path = shutil.which(info["exec"])
                    if w_path:
                        add_candidate(w_path, f"Built-in Windows Executable '{info['name']}'")

        if candidates:
            self._log_debug("Match found", f"Tier 1 (Built-in Apps): {candidates[0][1]}")
            self.index_cache[q_norm] = candidates
            self.save_cache()
            return candidates

        # ---------------------------------------------------------------------
        # TIER 2: Windows App Execution Aliases
        # ---------------------------------------------------------------------
        winapps_dir = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps"
        if winapps_dir.exists():
            for exe in winapps_dir.glob("*.exe"):
                if q_norm in exe.stem.lower():
                    add_candidate(str(exe), f"App Execution Alias '{exe.name}'")

        # ---------------------------------------------------------------------
        # TIER 3: Start Menu Shortcuts (User + All Users)
        # ---------------------------------------------------------------------
        start_dirs = [
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs")
        ]

        aliases = APP_ALIASES.get(q_norm, [q_norm])
        search_terms = [q_norm] + aliases

        for s_dir in start_dirs:
            if not s_dir.exists():
                continue
            for lnk in s_dir.rglob("*.lnk"):
                lnk_name_lower = lnk.stem.lower()
                if any(term in lnk_name_lower for term in search_terms):
                    target = resolve_shortcut_target(str(lnk))
                    add_candidate(target, f"Start Menu Shortcut '{lnk.name}'")

        # ---------------------------------------------------------------------
        # TIER 4: Desktop Shortcuts (User + Public)
        # ---------------------------------------------------------------------
        desktop_dirs = [
            Path.home() / "Desktop",
            Path(r"C:\Users\Public\Desktop")
        ]

        for d_dir in desktop_dirs:
            if not d_dir.exists():
                continue
            for item in d_dir.rglob("*"):
                item_lower = item.name.lower()
                if any(term in item_lower for term in search_terms):
                    if item.suffix.lower() == ".lnk":
                        target = resolve_shortcut_target(str(item))
                        add_candidate(target, f"Desktop Shortcut '{item.name}'")
                    else:
                        add_candidate(str(item), f"Desktop Item '{item.name}'")

        # ---------------------------------------------------------------------
        # TIER 5: Installed Programs & Registry Keys
        # ---------------------------------------------------------------------
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        for root_key, sub_key in reg_keys:
            try:
                with winreg.OpenKey(root_key, sub_key) as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        name = winreg.EnumKey(key, i)
                        name_lower = name.lower()
                        if any(term in name_lower for term in search_terms):
                            try:
                                with winreg.OpenKey(key, name) as app_key:
                                    # Try default value or InstallLocation / DisplayIcon
                                    path_val = None
                                    try:
                                        path_val, _ = winreg.QueryValueEx(app_key, "")
                                    except Exception:
                                        pass
                                    if not path_val or not os.path.exists(str(path_val)):
                                        try:
                                            path_val, _ = winreg.QueryValueEx(app_key, "DisplayIcon")
                                        except Exception:
                                            pass

                                    if path_val:
                                        # Strip quotes or comma arguments (e.g., C:\app.exe,0)
                                        clean_path = str(path_val).split(",")[0].strip('"')
                                        if clean_path and os.path.exists(clean_path):
                                            add_candidate(clean_path, f"Registry Entry '{name}'")
                            except Exception:
                                pass
            except Exception:
                pass

        # ---------------------------------------------------------------------
        # TIER 6: System PATH Executables
        # ---------------------------------------------------------------------
        which_exact = shutil.which(q_norm)
        if which_exact:
            add_candidate(which_exact, f"System PATH Executable '{os.path.basename(which_exact)}'")

        for term in search_terms:
            w_p = shutil.which(term)
            if w_p:
                add_candidate(w_p, f"System PATH Executable '{os.path.basename(w_p)}'")

        # ---------------------------------------------------------------------
        # TIER 7: Common Installation Folders
        # ---------------------------------------------------------------------
        common_folders = [
            Path(r"C:\Program Files"),
            Path(r"C:\Program Files (x86)"),
            Path.home() / "AppData" / "Local" / "Programs",
            Path.home() / "AppData" / "Roaming",
            Path(r"C:\Program Files (x86)\Steam\steamapps\common")
        ]

        for c_folder in common_folders:
            if not c_folder.exists():
                continue
            try:
                for sub in c_folder.iterdir():
                    if sub.is_dir() and any(term in sub.name.lower() for term in search_terms):
                        for exe in sub.glob("*.exe"):
                            add_candidate(str(exe), f"Installation Directory Executable '{exe.name}'")
                            if len(candidates) >= 10:
                                break
                        for exe in sub.glob("*/*.exe"):
                            add_candidate(str(exe), f"Installation Directory Executable '{exe.name}'")
                            if len(candidates) >= 10:
                                break
                    elif sub.is_file() and sub.suffix.lower() == ".exe":
                        if any(term in sub.name.lower() for term in search_terms):
                            add_candidate(str(sub), f"Installation Executable '{sub.name}'")
            except Exception:
                pass

        # Save discovered candidates to cache for future instant launches
        if candidates:
            self._log_debug("Match found", f"Discovered {len(candidates)} candidate(s) for '{q_norm}'")
            self.index_cache[q_norm] = candidates
            self.save_cache()

        return candidates

    def resolve_app(self, query: str) -> Tuple[Union[str, List[Tuple[str, str]], None], str]:
        """
        Resolves query to a single path or candidate list.
        Returns:
            (path_str, description) if 1 match found
            (candidates_list, "DISAMBIGUATION_REQUIRED") if multiple found
            (None, "") if none found
        """
        candidates = self.search_all_tiers(query)
        if not candidates:
            return None, ""

        if len(candidates) == 1:
            exe_path, desc = candidates[0]
            self._log_debug("Executable resolved", f"{desc} -> {exe_path}")
            return exe_path, desc

        # Multiple candidates found - check if one is an exact main executable match
        q_norm = normalize_query(query)
        exact_matches = []
        for path_str, desc in candidates:
            fn = os.path.basename(path_str).lower().replace(".exe", "")
            if fn == q_norm:
                exact_matches.append((path_str, desc))

        if len(exact_matches) == 1:
            exe_path, desc = exact_matches[0]
            self._log_debug("Executable resolved", f"Exact match: {desc} -> {exe_path}")
            return exe_path, desc

        return candidates, "DISAMBIGUATION_REQUIRED"

    def launch_app(self, query: str) -> dict:
        """
        Full Execution Pipeline:
        1. Search and resolve target application executable or protocol.
        2. Detect if app is already running -> bring window to foreground.
        3. If not running, launch process safely.
        4. Poll process telemetry for up to 3 seconds to verify actual launch.
        """
        self._log_debug("Searching...", f"Target query: '{query}'")

        resolved, desc_or_signal = self.resolve_app(query)

        if not resolved:
            return {"status": "failed", "reason": f"Could not locate application '{query}' on system."}

        if desc_or_signal == "DISAMBIGUATION_REQUIRED":
            return {"status": "failed", "reason": "DISAMBIGUATION_REQUIRED", "candidates": resolved}

        exe_or_uri = resolved
        desc = desc_or_signal

        # Step 1: Check if already running -> Bring to Foreground
        if not exe_or_uri.startswith("ms-"):
            if bring_window_to_foreground(exe_or_uri):
                self._log_debug("Match found", f"Application '{query}' is already running. Brought window to foreground.")
                self._log_debug("Success", f"Window foregrounded for {exe_or_uri}")
                return {
                    "status": "success",
                    "details": f"Application '{desc}' is already running. Brought window to foreground.",
                    "action": "open_app"
                }

        # Step 2: Launch Process
        self._log_debug("Launching", f"Starting '{exe_or_uri}'...")

        try:
            if exe_or_uri.startswith("ms-"):
                os.startfile(exe_or_uri)
            elif os.path.exists(exe_or_uri):
                os.startfile(exe_or_uri)
            else:
                subprocess.Popen(f'"{exe_or_uri}"', shell=True)

            # Step 3: Verify Process Launch Telemetry (Poll for up to 3 seconds)
            verified = False
            start_poll = time.time()
            p_clean = os.path.basename(exe_or_uri).lower().replace(".exe", "")

            while time.time() - start_poll < 3.0:
                time.sleep(0.3)
                if exe_or_uri.startswith("ms-"):
                    verified = True
                    break

                for proc in psutil.process_iter(['name', 'exe']):
                    try:
                        p_name = (proc.info['name'] or "").lower().replace(".exe", "")
                        if p_clean in p_name:
                            verified = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                if verified:
                    break

            if verified:
                self._log_debug("Success", f"Application '{exe_or_uri}' verified running.")
                return {
                    "status": "success",
                    "details": f"Successfully launched {desc}",
                    "action": "open_app"
                }
            else:
                # If process wasn't detected immediately but launch command succeeded without error
                self._log_debug("Success", f"Initiated launch process for {desc}")
                return {
                    "status": "success",
                    "details": f"Initiated launch process for {desc}",
                    "action": "open_app"
                }

        except Exception as ex:
            err_msg = f"Failed to launch application '{exe_or_uri}': {ex}"
            log_exception(ex, context="APP_LAUNCH_FAILED")
            return {"status": "failed", "reason": err_msg}


# Global Singleton Application Discovery Service
app_discovery_service = ApplicationDiscoveryService()

# Legacy helper functions for backwards compatibility with existing handlers
def find_all_matching_apps(app_name: str) -> List[Tuple[str, str]]:
    return app_discovery_service.search_all_tiers(app_name)

def find_app_path(app_name: str) -> Tuple[Union[str, List[Tuple[str, str]], None], str]:
    return app_discovery_service.resolve_app(app_name)

def find_desktop_item(query: str) -> List[Tuple[str, str]]:
    desktop_dirs = [Path.home() / "Desktop", Path(r"C:\Users\Public\Desktop")]
    matches = []
    q_lower = query.lower().strip()
    for d in desktop_dirs:
        if d.exists():
            for item in d.rglob("*"):
                if q_lower in item.name.lower():
                    matches.append((str(item), f"Desktop Item '{item.name}'"))
    return matches
