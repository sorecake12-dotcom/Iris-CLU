"""
IRIS AI - Robust Application Discovery & Launch Engine
Redesigned Application Discovery Service supporting multi-tiered search,
shortcut resolution, registry indexing, window foregrounding for running apps,
persistent app path caching, process verification, helper filtering, and automatic priority resolution.
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
        "aliases": ["explorer", "file explorer", "explorer.exe", "windows explorer", "my computer", "this pc", "files"],
        "path": r"C:\Windows\explorer.exe",
        "exec": "explorer.exe",
        "type": "executable"
    },
    "edge": {
        "name": "Microsoft Edge",
        "aliases": ["edge", "microsoft edge", "msedge", "msedge.exe"],
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
        "aliases": ["wt", "windows terminal", "wt.exe", "terminal"],
        "path": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"),
        "exec": "WindowsTerminal.exe",
        "type": "executable"
    }
}

# Comprehensive App Alias Database
APP_ALIASES: Dict[str, List[str]] = {
    "spotify": ["spotify.exe", "Spotify"],
    "music": ["spotify.exe", "Spotify"],
    "songs": ["spotify.exe", "Spotify"],
    "song": ["spotify.exe", "Spotify"],
    "chrome": ["chrome.exe", "Google Chrome"],
    "google": ["chrome.exe", "Google Chrome"],
    "google chrome": ["chrome.exe"],
    "browser": ["chrome.exe", "msedge.exe", "firefox.exe"],
    "firefox": ["firefox.exe", "Mozilla Firefox"],
    "edge": ["msedge.exe", "Microsoft Edge"],
    "microsoft edge": ["msedge.exe"],
    "vscode": ["code.exe", "Visual Studio Code"],
    "code": ["code.exe", "Visual Studio Code"],
    "vs code": ["code.exe", "Visual Studio Code"],
    "visual studio code": ["code.exe"],
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

# Patterns of helper / auxiliary / non-user executables to IGNORE
HELPER_PATTERNS = [
    r"_cli\.exe$", r"cli\.exe$", r"helper\.exe$", r"updater\.exe$", r"crash_handler\.exe$",
    r"crashpad.*\.exe$", r"service\.exe$", r"launcher\.exe$", r"uninstall.*\.exe$",
    r"setup\.exe$", r"install.*\.exe$", r"update\.exe$", r"nwjc\.exe$", r"elevate\.exe$",
    r"migrate\.exe$", r"background.*\.exe$", r"daemon\.exe$", r"server\.exe$",
    r"cef.*\.exe$", r"gpu.*\.exe$", r"worker.*\.exe$"
]


def is_helper_executable(exe_name_or_path: str) -> bool:
    """Check whether executable is a background helper / CLI / updater process to ignore."""
    if not exe_name_or_path or exe_name_or_path.startswith("ms-"):
        return False
    name = os.path.basename(exe_name_or_path).lower()
    for pattern in HELPER_PATTERNS:
        if re.search(pattern, name):
            return True
    return False


def canonicalize_path(p: str) -> str:
    """Normalize file path for strict case-insensitive deduplication."""
    if p.startswith("ms-"):
        return p.lower()
    try:
        real = os.path.realpath(p)
        return os.path.normcase(os.path.abspath(real))
    except Exception:
        return os.path.normcase(os.path.abspath(p))


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
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    found_hwnd.append(hwnd)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

    if found_hwnd:
        target_hwnd = found_hwnd[0]
        ctypes.windll.user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(target_hwnd)
        ctypes.windll.user32.BringWindowToTop(target_hwnd)
        return True

    return False


class ApplicationDiscoveryService:
    """Comprehensive Multi-Tiered Application Discovery & Launch Service for IRIS AI."""

    def __init__(self):
        self.cache_file = Path.home() / ".iris_app_index.json"
        self.index_cache: Dict[str, dict] = {}
        self.load_cache()

    def _log_debug(self, stage: str, message: str):
        """Format debug logs according to spec."""
        if getattr(config, "DEBUG_MODE", False):
            from rich.console import Console
            c = Console()
            c.print(f"[bold cyan][APP] {stage}[/bold cyan] [dim white]{message}[/dim white]")
        debug_log(f"{stage}: {message}", category="APP")

    def load_cache(self):
        """Load persistent application cache from disk."""
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

    def search_all_tiers(self, query: str) -> List[Tuple[str, str, int]]:
        """
        Search for applications across structured tiers in priority order:
        Returns list of tuples: (canonical_path, description, priority_score)
        """
        q_norm = normalize_query(query)
        if not q_norm:
            return []

        # Fast Persistent Cache Check
        if q_norm in self.index_cache:
            entry = self.index_cache[q_norm]
            if isinstance(entry, dict):
                path_str = entry.get("path")
                desc = entry.get("desc", f"Cached App '{q_norm}'")
                if path_str and (path_str.startswith("ms-") or os.path.exists(path_str)):
                    self._log_debug("Cache hit", f"Resolved '{q_norm}' -> {path_str}")
                    return [(path_str, desc, 100)]
            elif isinstance(entry, list) and entry:
                first = entry[0]
                if isinstance(first, (list, tuple)) and len(first) >= 2:
                    p_str, d_str = first[0], first[1]
                    if p_str and (p_str.startswith("ms-") or os.path.exists(p_str)):
                        return [(p_str, d_str, 100)]

        candidates: List[Tuple[str, str, int]] = []
        seen_canon: Set[str] = set()

        def add_candidate(path_val: str, desc: str, score: int):
            if is_helper_executable(path_val):
                return
            canon = canonicalize_path(path_val)
            if canon not in seen_canon:
                seen_canon.add(canon)
                candidates.append((path_val, desc, score))

        # TIER 1: Built-in Windows Applications (Score 90)
        for app_key, info in BUILTIN_APPS.items():
            if q_norm == app_key or any(alias == q_norm for alias in info["aliases"]):
                if info.get("protocol"):
                    add_candidate(info["protocol"], f"Built-in App '{info['name']}'", 90)
                elif info.get("path") and os.path.exists(info["path"]):
                    add_candidate(info["path"], f"Built-in App '{info['name']}'", 90)
                elif info.get("fallback_paths"):
                    for fp in info["fallback_paths"]:
                        if os.path.exists(fp):
                            add_candidate(fp, f"Built-in App '{info['name']}'", 90)
                            break
                elif info.get("exec"):
                    w_path = shutil.which(info["exec"])
                    if w_path:
                        add_candidate(w_path, f"Built-in Executable '{info['name']}'", 90)

        # TIER 2: Start Menu Shortcuts (Score 80)
        start_dirs = [
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs")
        ]
        aliases = APP_ALIASES.get(q_norm, [q_norm])
        search_terms = list(dict.fromkeys([q_norm] + aliases))

        for s_dir in start_dirs:
            if not s_dir.exists():
                continue
            for lnk in s_dir.rglob("*.lnk"):
                lnk_name_lower = lnk.stem.lower()
                if any(term in lnk_name_lower for term in search_terms):
                    target = resolve_shortcut_target(str(lnk))
                    if not is_helper_executable(target):
                        add_candidate(target, f"Start Menu App '{lnk.stem}'", 80)

        # TIER 3: Desktop Shortcuts (Score 70)
        desktop_dirs = [Path.home() / "Desktop", Path(r"C:\Users\Public\Desktop")]
        for d_dir in desktop_dirs:
            if not d_dir.exists():
                continue
            for item in d_dir.rglob("*"):
                if any(term in item.name.lower() for term in search_terms):
                    if item.suffix.lower() == ".lnk":
                        target = resolve_shortcut_target(str(item))
                        if not is_helper_executable(target):
                            add_candidate(target, f"Desktop App '{item.stem}'", 70)
                    elif item.suffix.lower() == ".exe":
                        if not is_helper_executable(str(item)):
                            add_candidate(str(item), f"Desktop App '{item.stem}'", 70)

        # TIER 4: Registry App Paths (Score 60)
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for root_key, sub_key in reg_keys:
            try:
                with winreg.OpenKey(root_key, sub_key) as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        name = winreg.EnumKey(key, i)
                        if any(term in name.lower() for term in search_terms):
                            try:
                                with winreg.OpenKey(key, name) as app_key:
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
                                        clean_path = str(path_val).split(",")[0].strip('"')
                                        if clean_path and os.path.exists(clean_path):
                                            add_candidate(clean_path, f"Registry App '{name}'", 60)
                            except Exception:
                                pass
            except Exception:
                pass

        # TIER 5: System PATH Executables (Score 50)
        for term in search_terms:
            w_p = shutil.which(term)
            if w_p:
                add_candidate(w_p, f"PATH Executable '{os.path.basename(w_p)}'", 50)

        # TIER 6: Windows App Execution Aliases (Score 40)
        winapps_dir = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps"
        if winapps_dir.exists():
            for exe in winapps_dir.glob("*.exe"):
                if any(term in exe.stem.lower() for term in search_terms):
                    add_candidate(str(exe), f"Windows App '{exe.stem}'", 40)

        # TIER 7: Common Installation Folders (Score 30)
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
                            if not is_helper_executable(str(exe)):
                                add_candidate(str(exe), f"Installed App '{sub.name}'", 30)
                                break
            except Exception:
                pass

        # Sort candidates by priority score descending
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates

    def resolve_app(self, query: str) -> Tuple[Optional[str], str]:
        """
        Resolves query automatically to the single best priority application path.
        Guarantees automatic resolution for Spotify, Chrome, Edge, WhatsApp, VS Code, Discord, etc.
        """
        q_norm = normalize_query(query)
        candidates = self.search_all_tiers(query)
        if not candidates:
            return None, ""

        # Auto-select the top-priority candidate
        best_path, best_desc, _ = candidates[0]

        # Save to persistent cache for instant launch next time
        self.index_cache[q_norm] = {"path": best_path, "desc": best_desc}
        self.save_cache()

        self._log_debug("Resolved app", f"'{query}' -> {best_path} ({best_desc})")
        return best_path, best_desc

    def launch_app(self, query: str) -> dict:
        """
        Full Automatic App Launch Pipeline:
        1. Check if application is ALREADY running -> bring top-level window to front.
        2. Resolve target executable path using automatic priority engine.
        3. Launch process cleanly.
        4. Return clean natural status dict.
        """
        q_norm = normalize_query(query)
        self._log_debug("Searching...", f"Target query: '{query}'")

        # Step 1: Running Window Check -> Focus immediately if already running!
        if bring_window_to_foreground(q_norm):
            self._log_debug("Window focused", f"Application '{query}' already running. Brought window to front.")
            return {
                "status": "success",
                "details": f"✓ {query.title()} opened.",
                "action": "open_app"
            }

        # Step 2: Resolve Application Executable Path
        exe_path, desc = self.resolve_app(query)

        if not exe_path:
            return {"status": "failed", "reason": f"I couldn't find an application named '{query}'."}

        # Step 3: Check if resolved exe is running -> Bring window to front
        if not exe_path.startswith("ms-"):
            if bring_window_to_foreground(exe_path):
                return {
                    "status": "success",
                    "details": f"Opened {query.title()}.",
                    "action": "open_app"
                }

        # Step 4: Launch Process
        self._log_debug("Launching", f"Starting '{exe_path}'...")
        try:
            if exe_path.startswith("ms-"):
                os.startfile(exe_path)
            elif os.path.exists(exe_path):
                os.startfile(exe_path)
            else:
                subprocess.Popen(f'"{exe_path}"', shell=True)

            # Briefly poll (up to 1.5s) to bring new window to top
            time.sleep(0.8)
            bring_window_to_foreground(exe_path)

            return {
                "status": "success",
                "details": f"Opened {query.title()}.",
                "action": "open_app"
            }

        except Exception as ex:
            log_exception(ex, context="APP_LAUNCH_FAILED")
            return {"status": "failed", "reason": f"I couldn't launch '{query}'."}


# Global Singleton Application Discovery Service
app_discovery_service = ApplicationDiscoveryService()

# Legacy helper functions for backwards compatibility with existing handlers
def find_all_matching_apps(app_name: str) -> List[Tuple[str, str]]:
    return [(path, desc) for path, desc, _ in app_discovery_service.search_all_tiers(app_name)]

def find_app_path(app_name: str) -> Tuple[Optional[str], str]:
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
