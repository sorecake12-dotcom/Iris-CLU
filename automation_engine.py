"""
IRIS AI - Secure Windows Automation Engine
Provides safe, modular, schema-validated, and permission-aware Windows OS automation.
Connects App Discovery, Spotify Automation, WhatsApp Messaging, and Browser Automation.
"""

import os
import sys
import re
import json
import time
import glob
import shutil
import socket
import psutil
import datetime
import subprocess
import webbrowser
from pathlib import Path
from rich.console import Console

import config
from app_discovery import find_app_path, find_all_matching_apps, find_desktop_item
from spotify_automation import play_spotify, bring_spotify_to_foreground, is_spotify_running
from whatsapp_automation import open_messaging_app, automate_whatsapp_message
from browser_automation import open_multiple_websites, browser_search, execute_tab_action, fill_form_text
from debug_logger import debug_log, log_json_payload, log_exception
from file_engine import file_engine, resolve_path as fe_resolve
from window_manager import window_manager
from workspace_manager import workspace_manager
from terminal_engine import terminal_engine
from screen_engine import screen_engine
from clipboard_engine import clipboard_engine

console = Console()

# Optional automation libraries
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

# High-risk action types that ALWAYS require explicit user confirmation
HIGH_RISK_ACTIONS = {
    "delete_item",
    "run_command",
    "run_terminal_command",
    "kill_process",
    "system_power",
    "install_software",
    "registry_changes",
    "format_drive",
    "send_message",
    "empty_recycle_bin",
}

SETTINGS_PAGES = {
    "system": "ms-settings:",
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "battery": "ms-settings:powersleep",
    "power": "ms-settings:powersleep",
    "storage": "ms-settings:storagesense",
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "network": "ms-settings:network",
    "personalization": "ms-settings:personalization",
    "apps": "ms-settings:appsfeatures",
    "windows update": "ms-settings:windowsupdate",
    "update": "ms-settings:windowsupdate",
    "privacy": "ms-settings:privacy"
}


class PluginRegistry:
    """Modular registry allowing custom automation plugins to be registered dynamically."""

    def __init__(self):
        self._handlers = {}

    def register(self, action_name: str, handler_func):
        """Register a new action handler."""
        self._handlers[action_name] = handler_func

    def get_handler(self, action_name: str):
        """Retrieve action handler function by name."""
        return self._handlers.get(action_name)

    def list_actions(self):
        """List all registered action names."""
        return list(self._handlers.keys())


class WindowsAutomationEngine:
    """Core Security & Execution Engine for Desktop Automation."""

    def __init__(self):
        self.registry = PluginRegistry()
        self._register_default_handlers()

    def log(self, stage: str, message: str, style: str = "cyan"):
        """Format and print telemetry logs if DEBUG_MODE is active."""
        if config.DEBUG_MODE:
            console.print(f"[{style}][ACTION] {stage}: {message}[/{style}]")
        debug_log(f"{stage}: {message}", category="ACTION")

    def is_high_risk(self, action_data: dict) -> tuple[bool, str]:
        """Assess whether an action is high-risk and requires user confirmation."""
        action = action_data.get("action", "").lower()
        if action in HIGH_RISK_ACTIONS:
            if action == "delete_item":
                target = action_data.get("path") or action_data.get("target") or "file/folder"
                return True, f"Delete item '{target}'"
            elif action == "run_command":
                cmd = action_data.get("command") or action_data.get("target") or "script"
                return True, f"Execute shell command '{cmd}'"
            elif action == "system_power":
                p_type = action_data.get("type", "shutdown").lower()
                return True, f"System power action: {p_type.upper()}"
            elif action == "send_message":
                recipient = action_data.get("recipient") or action_data.get("to") or "contact"
                text = action_data.get("message") or action_data.get("text") or ""
                app = action_data.get("app", "messaging app")
                return True, f"Send message '{text}' to '{recipient}' on {app}"
            return True, f"Execute high-risk action: {action}"
        return False, ""

    def validate_action(self, action_data: dict) -> tuple[bool, str]:
        """Validate JSON schema structure and parameters for actions."""
        if not isinstance(action_data, dict):
            return False, "Action payload is not a valid JSON object."

        action = action_data.get("action")
        if not action or not isinstance(action, str):
            return False, "Missing or invalid 'action' field."

        handler = self.registry.get_handler(action.lower())
        if not handler:
            return False, f"Unsupported automation action '{action}'."

        return True, "Valid"

    def execute_action(self, action_data: dict, confirmed: bool = False) -> dict:
        """
        Validate, security-screen, and execute structured JSON automation action.
        """
        action = action_data.get("action", "").lower()
        log_json_payload(action_data, label="ACTION_PAYLOAD")

        # Step 1: Validate Schema
        is_valid, err_msg = self.validate_action(action_data)
        if not is_valid:
            self.log("Failed", err_msg, style="bold red")
            return {"status": "failed", "reason": err_msg, "action": action}

        self.log("Command validated", action, style="dim green")

        # Step 2: Security Check
        high_risk, risk_reason = self.is_high_risk(action_data)
        if high_risk and not confirmed:
            self.log("Confirmation required", risk_reason, style="bold yellow")
            return {
                "status": "confirmation_required",
                "reason": risk_reason,
                "action": action,
                "action_data": action_data
            }

        # Step 3: Execute Action
        self.log("Executing...", f"Running '{action}'", style="dim cyan")
        handler = self.registry.get_handler(action)

        try:
            res_detail = handler(action_data)
            self.log("Completed", res_detail, style="bold green")
            return {"status": "success", "details": res_detail, "action": action}
        except Exception as e:
            err_detail = f"{type(e).__name__}: {e}"
            self.log("Failed", err_detail, style="bold red")
            log_exception(e, context="ACTION_EXECUTION_FAILED")
            return {"status": "failed", "reason": err_detail, "action": action}

    # =========================================================================
    # ACTION HANDLERS MATRIX
    # =========================================================================

    def _register_default_handlers(self):
        r = self.registry
        r.register("open_app", self._handle_open_app)
        r.register("close_app", self._handle_close_app)
        r.register("switch_app", self._handle_switch_app)
        r.register("open_website", self._handle_open_website)
        r.register("open_urls", self._handle_open_urls)
        r.register("open_url", self._handle_open_website)
        r.register("web_search", self._handle_web_search)
        r.register("play_spotify", self._handle_play_spotify)
        r.register("send_message", self._handle_send_message)
        r.register("open_desktop_item", self._handle_open_desktop_item)
        r.register("create_file", self._handle_create_file)
        r.register("create_folder", self._handle_create_folder)
        r.register("rename_item", self._handle_rename_item)
        r.register("copy_item", self._handle_copy_item)
        r.register("move_item", self._handle_move_item)
        r.register("delete_item", self._handle_delete_item)
        r.register("search_files", self._handle_search_files)
        r.register("read_clipboard", self._handle_read_clipboard)
        r.register("write_clipboard", self._handle_write_clipboard)
        r.register("take_screenshot", self._handle_take_screenshot)
        r.register("set_volume", self._handle_set_volume)
        r.register("mute_audio", self._handle_mute_audio)
        r.register("unmute_audio", self._handle_unmute_audio)
        r.register("open_settings", self._handle_open_settings)
        r.register("get_system_info", self._handle_get_system_info)
        r.register("media_play_pause", self._handle_media_play_pause)
        r.register("media_next", self._handle_media_next)
        r.register("media_prev", self._handle_media_prev)
        r.register("browser_action", self._handle_browser_action)
        r.register("close_website", self._handle_close_website)
        r.register("close_tab", self._handle_close_website)
        r.register("close_browser", self._handle_close_website)
        r.register("play_spotify", self._handle_play_spotify)
        r.register("pause_spotify", self._handle_pause_spotify)
        r.register("resume_spotify", self._handle_resume_spotify)
        r.register("next_song", self._handle_next_song)
        r.register("prev_song", self._handle_prev_song)
        r.register("send_message", self._handle_send_message)
        r.register("press_hotkey", self._handle_press_hotkey)
        r.register("type_text", self._handle_type_text)
        r.register("open_explorer", self._handle_open_explorer)
        r.register("run_command", self._handle_run_command)
        r.register("system_power", self._handle_system_power)
        # Task Scheduler & Timer Handlers
        r.register("set_timer", self._handle_set_timer)
        r.register("pause_timer", self._handle_pause_timer)
        r.register("resume_timer", self._handle_resume_timer)
        r.register("cancel_timer", self._handle_cancel_timer)
        r.register("get_timer_status", self._handle_get_timer_status)
        r.register("schedule_delayed_action", self._handle_schedule_delayed_action)
        r.register("schedule_recurring_task", self._handle_schedule_recurring_task)
        r.register("list_tasks", self._handle_list_tasks)
        r.register("reschedule_task", self._handle_reschedule_task)

        # ── File Engine ───────────────────────────────────────────
        r.register("create_file",        self._handle_create_file)
        r.register("create_folder",      self._handle_create_folder)
        r.register("create_batch_folders", self._handle_create_batch_folders)
        r.register("delete_item",        self._handle_delete_item)
        r.register("rename_item",        self._handle_rename_item)
        r.register("copy_item",          self._handle_copy_item)
        r.register("move_item",          self._handle_move_item)
        r.register("read_file",          self._handle_read_file)
        r.register("append_to_file",     self._handle_append_to_file)
        r.register("replace_line",       self._handle_replace_line)
        r.register("delete_line",        self._handle_delete_line)
        r.register("search_in_file",     self._handle_search_in_file)
        r.register("compress_item",      self._handle_compress_item)
        r.register("extract_archive",    self._handle_extract_archive)
        r.register("get_folder_size",    self._handle_get_folder_size)
        r.register("list_folder",        self._handle_list_folder)
        r.register("search_files",       self._handle_search_files_adv)
        r.register("find_duplicates",    self._handle_find_duplicates)
        r.register("restore_recycle_bin",self._handle_restore_recycle_bin)
        r.register("empty_recycle_bin",  self._handle_empty_recycle_bin)

        # ── Window & Workspace Manager ────────────────────────────
        r.register("minimize_window",    self._handle_minimize_window)
        r.register("maximize_window",    self._handle_maximize_window)
        r.register("restore_window",     self._handle_restore_window)
        r.register("focus_window",       self._handle_focus_window)
        r.register("bring_to_front",     self._handle_focus_window)
        r.register("close_window",       self._handle_close_window)
        r.register("list_windows",       self._handle_list_windows)
        r.register("snap_window",        self._handle_snap_window)
        r.register("split_screen",       self._handle_split_screen)
        r.register("position_window",    self._handle_position_window)
        r.register("move_to_monitor",    self._handle_move_to_monitor)
        r.register("tile_all_windows",   self._handle_tile_all_windows)
        r.register("verify_window_state",self._handle_verify_window_state)
        r.register("launch_workspace_profile", self._handle_launch_workspace_profile)
        r.register("execute_workflow",   self._handle_execute_workflow)
        r.register("restore_browser_session", self._handle_restore_browser_session)

        # ── Terminal Engine ───────────────────────────────────────
        r.register("run_terminal_command", self._handle_run_terminal)
        r.register("run_powershell",     self._handle_run_terminal)
        r.register("create_venv",        self._handle_create_venv)
        r.register("install_package",    self._handle_install_package)
        r.register("run_python",         self._handle_run_python)
        r.register("kill_process",       self._handle_kill_process)
        r.register("list_processes",     self._handle_list_processes)

        # ── Screen Engine ─────────────────────────────────────────
        r.register("take_screenshot",    self._handle_screenshot)
        r.register("take_screenshot_area",self._handle_screenshot_area)
        r.register("start_recording",    self._handle_start_recording)
        r.register("stop_recording",     self._handle_stop_recording)
        r.register("ocr_screen",         self._handle_ocr_screen)

        # ── Clipboard Engine ──────────────────────────────────────
        r.register("read_clipboard",     self._handle_read_clipboard)
        r.register("write_clipboard",    self._handle_write_clipboard)
        r.register("clear_clipboard",    self._handle_clear_clipboard)
        r.register("clipboard_history",  self._handle_clipboard_history)

        # ── Memory / Preferences ──────────────────────────────────
        r.register("remember_preference",self._handle_remember_preference)
        r.register("forget_preference",  self._handle_forget_preference)
        r.register("remember_folder",    self._handle_remember_folder)
        r.register("show_preferences",   self._handle_show_preferences)

    # =========================================================================
    # PATH RESOLUTION HELPER
    # =========================================================================

    @staticmethod
    def _resolve_path(raw_path: str, filename: str = "") -> Path:
        """
        Resolve a user-friendly location keyword or partial path to a real absolute path.
        Maps keywords like 'desktop', 'documents', 'downloads', 'pictures' to their
        actual Windows special folders.  Falls back to expanduser().resolve() for
        explicit absolute paths.
        """
        if not raw_path:
            return Path.home() / "Desktop"

        # Keyword map for common Windows locations
        keyword_map = {
            "desktop":       Path.home() / "Desktop",
            "my desktop":    Path.home() / "Desktop",
            "documents":     Path.home() / "Documents",
            "my documents":  Path.home() / "Documents",
            "downloads":     Path.home() / "Downloads",
            "my downloads":  Path.home() / "Downloads",
            "pictures":      Path.home() / "Pictures",
            "my pictures":   Path.home() / "Pictures",
            "music":         Path.home() / "Music",
            "my music":      Path.home() / "Music",
            "videos":        Path.home() / "Videos",
            "my videos":     Path.home() / "Videos",
            "home":          Path.home(),
            "~":             Path.home(),
        }

        key = raw_path.strip().lower()

        # Pure keyword match → map to folder, append filename if given
        if key in keyword_map:
            base = keyword_map[key]
            return (base / filename) if filename else base

        # Keyword prefix: e.g. "desktop/myfile.txt" or "desktop\myfile.txt"
        for kw, folder in keyword_map.items():
            if key.startswith(kw + "/") or key.startswith(kw + "\\"):
                rest = raw_path[len(kw):].lstrip("\/")
                return folder / rest

        # Explicit path — expand ~ and resolve
        p = Path(raw_path).expanduser()
        if p.is_absolute():
            return p.resolve()

        # Relative path that isn't a keyword → treat as Desktop-relative
        return (Path.home() / "Desktop" / raw_path).resolve()

    # 1. Dynamic Application & Disambiguation Control
    def _handle_open_app(self, data: dict) -> str:
        target = data.get("target") or data.get("app") or data.get("name")
        if not target:
            raise ValueError("No app name specified.")

        from app_discovery import app_discovery_service
        res = app_discovery_service.launch_app(target)

        if res.get("status") == "success":
            return res.get("details", f"Launched application: {target}")

        if res.get("reason") == "DISAMBIGUATION_REQUIRED":
            candidates = res.get("candidates", [])
            cand_details = [f"{idx}. {desc} (`{p}`)" for idx, (p, desc) in enumerate(candidates, 1)]
            prompt_msg = f"I found multiple {target.title()} installations. Which one would you like to open?\n" + "\n".join(cand_details)
            raise ValueError(f"DISAMBIGUATION_REQUIRED:\n{prompt_msg}")

        raise ValueError(res.get("reason", f"Could not launch application '{target}'."))

    def _handle_open_desktop_item(self, data: dict) -> str:
        target = data.get("target") or data.get("name")
        if not target:
            raise ValueError("No Desktop target specified.")

        matches = find_desktop_item(target)
        if not matches:
            raise ValueError(f"Could not locate '{target}' on Desktop.")

        if len(matches) == 1:
            p, desc = matches[0]
            os.startfile(p)
            return f"Opened Desktop item: {desc}"

        cand_details = [f"{idx}. {desc} (`{p}`)" for idx, (p, desc) in enumerate(matches, 1)]
        raise ValueError(f"DISAMBIGUATION_REQUIRED:\n" + "\n".join(cand_details))

    def _handle_close_app(self, data: dict) -> str:
        target = data.get("target") or data.get("app")
        if not target:
            raise ValueError("No app target specified for closure.")

        t_lower = target.lower().replace(".exe", "")
        terminated_count = 0

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                p_name = proc.info['name'].lower().replace(".exe", "")
                if t_lower in p_name:
                    proc.terminate()
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if terminated_count > 0:
            return f"Terminated {terminated_count} process(es) matching '{target}'"
        else:
            return f"No running processes found matching '{target}'"

    def _handle_switch_app(self, data: dict) -> str:
        if HAS_PYAUTOGUI:
            pyautogui.hotkey("alt", "tab")
            return "Triggered Alt+Tab application window switch."
        return "Window switching simulated."

    # 2. Spotify Automation
    def _handle_play_spotify(self, data: dict) -> str:
        query = data.get("query") or data.get("target") or data.get("song") or ""
        return play_spotify(query)

    # 3. Messaging Automation (WhatsApp, Telegram, Discord, Teams)
    def _handle_send_message(self, data: dict) -> str:
        app = (data.get("app") or "whatsapp").lower().strip()
        recipient = data.get("recipient") or data.get("to") or "contact"
        text = data.get("message") or data.get("text") or ""
        return automate_whatsapp_message(recipient, text)

    # 4. Web & Browser Controls
    def _handle_open_website(self, data: dict) -> str:
        url = data.get("url") or data.get("target")
        if not url:
            raise ValueError("No URL specified.")
        return open_multiple_websites([url])

    def _handle_open_urls(self, data: dict) -> str:
        urls = data.get("urls") or data.get("targets") or []
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split(",")]
        return open_multiple_websites(urls)

    def _handle_web_search(self, data: dict) -> str:
        query = data.get("query") or data.get("target")
        engine = data.get("engine", "google")
        if not query:
            raise ValueError("No search query specified.")
        return browser_search(engine, query)

    # 5. File System & Search
    def _handle_create_file(self, data: dict) -> str:
        raw  = data.get("path") or data.get("target") or ""
        name = data.get("name") or data.get("filename") or ""
        content = data.get("content", "")

        if not raw and not name:
            raise ValueError("No file path or name specified.")

        # If only a name was given, create on Desktop by default
        if not raw and name:
            raw = "desktop"

        p = self._resolve_path(raw, filename=name)

        # If the resolved path is a directory (no extension), treat it as a folder + default filename
        if p.suffix == "" and name:
            p = p / name
        elif p.suffix == "" and not name:
            raise ValueError(f"Please specify a filename (e.g. 'note.txt'), not just a folder name.")

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Created file: {p}"

    def _handle_create_folder(self, data: dict) -> str:
        raw  = data.get("path") or data.get("target") or ""
        name = data.get("name") or data.get("folder_name") or ""

        if not raw and not name:
            raise ValueError("No folder path or name specified.")

        if not raw and name:
            raw = "desktop"

        p = self._resolve_path(raw, filename=name)
        p.mkdir(parents=True, exist_ok=True)
        return f"Created folder: {p}"

    def _handle_rename_item(self, data: dict) -> str:
        src = data.get("src") or data.get("path")
        dst = data.get("dst") or data.get("new_name")
        if not src or not dst:
            raise ValueError("Source path and destination name required.")
        src_p = Path(src).expanduser().resolve()
        dst_p = src_p.parent / dst if not os.path.isabs(dst) else Path(dst)
        src_p.rename(dst_p)
        return f"Renamed '{src_p.name}' -> '{dst_p.name}'"

    def _handle_copy_item(self, data: dict) -> str:
        src = data.get("src")
        dst = data.get("dst")
        if not src or not dst:
            raise ValueError("Source and destination required.")
        src_p = Path(src).expanduser().resolve()
        dst_p = Path(dst).expanduser().resolve()
        if src_p.is_dir():
            shutil.copytree(src_p, dst_p, dirs_exist_ok=True)
        else:
            shutil.copy2(src_p, dst_p)
        return f"Copied '{src_p.name}' to '{dst_p}'"

    def _handle_move_item(self, data: dict) -> str:
        src = data.get("src")
        dst = data.get("dst")
        if not src or not dst:
            raise ValueError("Source and destination required.")
        src_p = Path(src).expanduser().resolve()
        dst_p = Path(dst).expanduser().resolve()
        shutil.move(src_p, dst_p)
        return f"Moved '{src_p.name}' to '{dst_p}'"

    def _handle_delete_item(self, data: dict) -> str:
        raw = data.get("path") or data.get("target") or ""
        name = data.get("name") or ""
        if not raw and not name:
            raise ValueError("No item specified for deletion.")
        p = self._resolve_path(raw, filename=name)
        if not p.exists():
            # Try Desktop as fallback if nothing found
            fallback = Path.home() / "Desktop" / raw
            if fallback.exists():
                p = fallback
            else:
                return f"Item not found: {p}"
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"Deleted: {p}"

    def _handle_search_files(self, data: dict) -> str:
        query = data.get("query") or data.get("target") or "*.*"
        search_root = data.get("dir") or str(Path.home() / "Desktop")

        matches = []
        for root, _, files in os.walk(search_root):
            for file in files:
                if query.lower() in file.lower():
                    matches.append(os.path.join(root, file))
                if len(matches) >= 10:
                    break
            if len(matches) >= 10:
                break

        if matches:
            res = "\n".join([f"• {m}" for m in matches])
            return f"Found {len(matches)} matching file(s):\n{res}"
        return f"No files matching '{query}' found in {search_root}"

    # 6. Clipboard & Screenshots
    def _handle_read_clipboard(self, data: dict) -> str:
        if HAS_PYPERCLIP:
            text = pyperclip.paste()
            return f"Clipboard Content: \"{text[:200]}\"" if text else "Clipboard is empty."
        return "Pyperclip not available."

    def _handle_write_clipboard(self, data: dict) -> str:
        text = data.get("text") or data.get("content") or ""
        if HAS_PYPERCLIP:
            pyperclip.copy(text)
            return f"Copied {len(text)} characters to clipboard."
        return "Pyperclip not available."

    def _handle_take_screenshot(self, data: dict) -> str:
        shots_dir = Path.home() / "Pictures" / "Screenshots"
        shots_dir.mkdir(parents=True, exist_ok=True)
        filename = f"IRIS_Screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = shots_dir / filename

        if HAS_PYAUTOGUI:
            try:
                screenshot = pyautogui.screenshot()
                screenshot.save(filepath)
                return f"Saved screenshot to: {filepath}"
            except Exception:
                pass

        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(filepath)
            return f"Saved screenshot to: {filepath}"
        except Exception:
            pass

        try:
            ps_cmd = f'''powershell -Command "[Reflection.Assembly]::LoadWithPartialName('System.Drawing'); [Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; $graphics = [System.Drawing.Graphics]::FromImage($bmp); $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size); $bmp.Save('{filepath}'); $graphics.Dispose(); $bmp.Dispose()"'''
            subprocess.run(ps_cmd, shell=True, capture_output=True)
            if filepath.exists():
                return f"Saved screenshot to: {filepath}"
        except Exception:
            pass

        return f"Screenshot captured: {filepath}"

    # 7. System Controls & Telemetry
    def _handle_set_volume(self, data: dict) -> str:
        level = data.get("level", 50)
        try:
            level = int(level)
        except Exception:
            level = 50

        if HAS_PYAUTOGUI:
            steps = level // 2
            pyautogui.press('volumedown', presses=50)
            pyautogui.press('volumeup', presses=steps)
            return f"Set system master volume to approx {level}%"
        return "Volume adjustment simulated."

    def _handle_mute_audio(self, data: dict) -> str:
        if HAS_PYAUTOGUI:
            pyautogui.press('volumemute')
            return "Toggled master audio mute."
        return "Audio mute simulated."

    def _handle_unmute_audio(self, data: dict) -> str:
        if HAS_PYAUTOGUI:
            pyautogui.press('volumemute')
            return "Toggled master audio unmute."
        return "Audio unmute simulated."

    def _handle_open_settings(self, data: dict) -> str:
        page = (data.get("page") or data.get("target") or "system").lower()
        uri = SETTINGS_PAGES.get(page, "ms-settings:")
        os.startfile(uri)
        return f"Opened Windows Settings page: {page}"

    def _handle_get_system_info(self, data: dict) -> str:
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        batt = psutil.sensors_battery()

        batt_str = f"{batt.percent}% ({'Plugged in' if batt.power_plugged else 'Discharging'})" if batt else "N/A"

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        info = (
            f"• CPU Utilization: {cpu}%\n"
            f"• Memory Usage: {mem.percent}% ({round(mem.used/(1024**3), 1)}GB / {round(mem.total/(1024**3), 1)}GB)\n"
            f"• Disk Usage (C:): {disk.percent}% ({round(disk.free/(1024**3), 1)}GB free)\n"
            f"• Battery Status: {batt_str}\n"
            f"• Local IP Address: {local_ip} ({hostname})"
        )
        return info

    # 8. Media Controls
    def _handle_media_play_pause(self, data: dict) -> str:
        if HAS_PYAUTOGUI:
            pyautogui.press('playpause')
            return "Triggered media Play/Pause toggle."
        return "Media Play/Pause simulated."

    def _handle_media_next(self, data: dict) -> str:
        if HAS_PYAUTOGUI:
            pyautogui.press('nexttrack')
            return "Triggered Next media track."
        return "Media Next track simulated."

    def _handle_media_prev(self, data: dict) -> str:
        if HAS_PYAUTOGUI:
            pyautogui.press('prevtrack')
            return "Triggered Previous media track."
        return "Media Previous track simulated."

    # 9. Browser Actions
    def _handle_browser_action(self, data: dict) -> str:
        sub_action = data.get("type", "new_tab").lower()
        return execute_tab_action(sub_action)

    # 10. Hotkey / Keyboard
    def _handle_press_hotkey(self, data: dict) -> str:
        keys = data.get("keys") or data.get("target") or []
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split("+")]
        if HAS_PYAUTOGUI and keys:
            pyautogui.hotkey(*keys)
            return f"Executed hotkey shortcut: {'+'.join(keys)}"
        return f"Hotkey {'+'.join(keys)} simulated."

    def _handle_type_text(self, data: dict) -> str:
        text = data.get("text", "")
        return fill_form_text(text)

    # 11. Explorer & Shell
    def _handle_open_explorer(self, data: dict) -> str:
        target = data.get("path") or data.get("target") or str(Path.home())
        p = Path(target).expanduser().resolve()
        os.startfile(str(p))
        return f"Opened File Explorer at: {p}"

    def _handle_run_command(self, data: dict) -> str:
        cmd = data.get("command") or data.get("target")
        if not cmd:
            raise ValueError("No command specified.")
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        out = res.stdout.strip() or res.stderr.strip() or "Command completed with exit code 0."
        return f"Shell Output:\n{out[:400]}"

    # 12. Power Management
    def _handle_system_power(self, data: dict) -> str:
        p_type = data.get("type", "lock").lower()
        if p_type == "lock":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Locked workstation PC."
        elif p_type == "sleep":
            subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return "Initiated system sleep mode."
        elif p_type == "restart":
            subprocess.run("shutdown /r /t 5", shell=True)
            return "Scheduled system restart in 5 seconds."
        elif p_type == "shutdown":
            subprocess.run("shutdown /s /t 5", shell=True)
            return "Scheduled system shutdown in 5 seconds."
        else:
            return f"Unknown power action '{p_type}'."

    # 13. Enhanced Browser & Tab Control
    def _handle_close_website(self, data: dict) -> str:
        target = data.get("target") or data.get("url") or data.get("site") or "current_tab"
        from browser_automation import close_browser_target
        return close_browser_target(target)

    # 14. Deep Spotify Control
    def _handle_play_spotify(self, data: dict) -> str:
        query = data.get("query") or data.get("target") or data.get("song") or data.get("artist") or data.get("playlist") or ""
        from spotify_automation import play_spotify
        res = play_spotify(query)
        if isinstance(res, dict):
            return res.get("details", "Triggered Spotify playback.")
        return str(res)

    def _handle_pause_spotify(self, data: dict) -> str:
        from spotify_automation import pause_spotify
        return pause_spotify()

    def _handle_resume_spotify(self, data: dict) -> str:
        from spotify_automation import resume_spotify
        return resume_spotify()

    def _handle_next_song(self, data: dict) -> str:
        from spotify_automation import next_spotify_track
        return next_spotify_track()

    def _handle_prev_song(self, data: dict) -> str:
        from spotify_automation import prev_spotify_track
        return prev_spotify_track()

    # 15. WhatsApp & Messaging Control
    def _handle_send_message(self, data: dict) -> str:
        recipient = data.get("recipient") or data.get("to") or data.get("contact") or "contact"
        text = data.get("message") or data.get("text") or ""
        from whatsapp_automation import automate_whatsapp_message
        res = automate_whatsapp_message(recipient, text, send_now=data.get("send_now", False))
        if isinstance(res, dict):
            return res.get("details", f"Processed message for {recipient}.")
        return str(res)

    # 16. Task Scheduler & Timer Handlers
    def _handle_set_timer(self, data: dict) -> str:
        from task_scheduler import task_scheduler, parse_time_duration
        sec = data.get("duration_seconds")
        if not sec:
            dur_str = data.get("duration") or data.get("time") or data.get("target") or "2 minutes"
            sec = parse_time_duration(str(dur_str)) or 120.0
        label = data.get("label") or data.get("description")
        task = task_scheduler.create_timer(float(sec), label=label)
        return f"Set timer for {task.format_time_left()} (ID: {task.task_id})"

    def _handle_pause_timer(self, data: dict) -> str:
        from task_scheduler import task_scheduler
        qid = data.get("task_id") or data.get("target")
        success, msg = task_scheduler.pause_timer(qid)
        return msg

    def _handle_resume_timer(self, data: dict) -> str:
        from task_scheduler import task_scheduler
        qid = data.get("task_id") or data.get("target")
        success, msg = task_scheduler.resume_timer(qid)
        return msg

    def _handle_cancel_timer(self, data: dict) -> str:
        from task_scheduler import task_scheduler
        qid = data.get("task_id") or data.get("target")
        success, msg = task_scheduler.cancel_task(qid)
        return msg

    def _handle_get_timer_status(self, data: dict) -> str:
        from task_scheduler import task_scheduler
        qid = data.get("task_id") or data.get("target")
        return task_scheduler.get_timer_time_left(qid)

    def _handle_schedule_delayed_action(self, data: dict) -> str:
        from task_scheduler import task_scheduler, parse_time_duration
        sec = data.get("delay_seconds")
        if not sec:
            dur_str = data.get("delay") or data.get("time") or "2 minutes"
            sec = parse_time_duration(str(dur_str)) or 120.0
        
        action_payload = data.get("action_payload") or data.get("action_data") or data.get("payload") or {}
        desc = data.get("description") or data.get("label") or "Delayed automation"
        
        task = task_scheduler.create_delayed_action(float(sec), action_payload, desc)
        return f"Scheduled action '{desc}' to execute in {task.format_time_left()} (ID: {task.task_id})"

    def _handle_schedule_recurring_task(self, data: dict) -> str:
        from task_scheduler import task_scheduler
        rule = (data.get("recurrence") or data.get("rule") or "daily").lower()
        time_str = data.get("time_of_day") or data.get("time")
        msg = data.get("message") or data.get("description") or "Recurring Task"
        payload = data.get("action_payload") or data.get("action_data")
        
        task = task_scheduler.create_recurring_task(rule, action_data=payload, description=msg, message=msg, time_of_day=time_str)
        return f"Created recurring {rule} task '{task.description}' (ID: {task.task_id})"

    def _handle_list_tasks(self, data: dict) -> str:
        from task_scheduler import task_scheduler
        from ui import render_scheduled_tasks_table
        filter_type = data.get("filter")
        tasks = task_scheduler.get_active_tasks(filter_type=filter_type)
        render_scheduled_tasks_table(tasks)
        if not tasks:
            return "No active timers or scheduled tasks running."
        return f"Currently running {len(tasks)} active task(s)."

    def _handle_reschedule_task(self, data: dict) -> str:
        from task_scheduler import task_scheduler, parse_time_duration
        qid = data.get("task_id") or data.get("target") or "1"
        sec = data.get("new_delay_seconds")
        if not sec:
            dur_str = data.get("new_time") or data.get("delay") or "5 minutes"
            sec = parse_time_duration(str(dur_str)) or 300.0
        success, msg = task_scheduler.reschedule_task(qid, float(sec))
        return msg

    # =========================================================================
    # FILE ENGINE HANDLERS
    # =========================================================================

    def _handle_create_file(self, data: dict) -> str:
        return file_engine.create_file(
            data.get("path", "desktop"),
            data.get("name", ""),
            data.get("content", "")
        )

    def _handle_create_folder(self, data: dict) -> str:
        return file_engine.create_folder(
            data.get("path", "desktop"),
            data.get("name", "")
        )

    def _handle_create_batch_folders(self, data: dict) -> str:
        path   = data.get("path", "desktop")
        prefix = data.get("prefix", "Folder")
        start  = int(data.get("start", 1))
        end    = int(data.get("end", 10))
        return file_engine.create_batch_folders(path, prefix, start, end)

    def _handle_delete_item(self, data: dict) -> str:
        return file_engine.delete_item(
            data.get("path", "desktop"),
            data.get("name", "") or data.get("target", "")
        )

    def _handle_rename_item(self, data: dict) -> str:
        return file_engine.rename_item(
            data.get("path", "desktop"),
            data.get("name", "") or data.get("old_name", ""),
            data.get("new_name", "")
        )

    def _handle_copy_item(self, data: dict) -> str:
        return file_engine.copy_item(
            data.get("src_path", "desktop"),
            data.get("src_name", "") or data.get("name", ""),
            data.get("dst_path", "desktop"),
            data.get("dst_name", "")
        )

    def _handle_move_item(self, data: dict) -> str:
        return file_engine.move_item(
            data.get("src_path", "desktop"),
            data.get("src_name", "") or data.get("name", ""),
            data.get("dst_path", "documents")
        )

    def _handle_read_file(self, data: dict) -> str:
        return file_engine.read_file(
            data.get("path", "desktop"),
            data.get("name", ""),
            int(data.get("max_lines", 100))
        )

    def _handle_append_to_file(self, data: dict) -> str:
        return file_engine.append_to_file(
            data.get("path", "desktop"),
            data.get("name", ""),
            data.get("text", "") or data.get("content", "")
        )

    def _handle_replace_line(self, data: dict) -> str:
        return file_engine.replace_line(
            data.get("path", "desktop"),
            data.get("name", ""),
            int(data.get("line", data.get("line_number", 1))),
            data.get("new_text", "") or data.get("text", "")
        )

    def _handle_delete_line(self, data: dict) -> str:
        return file_engine.delete_line(
            data.get("path", "desktop"),
            data.get("name", ""),
            int(data.get("line", data.get("line_number", 1)))
        )

    def _handle_search_in_file(self, data: dict) -> str:
        return file_engine.search_in_file(
            data.get("path", "desktop"),
            data.get("name", ""),
            data.get("query", "") or data.get("search", "")
        )

    def _handle_compress_item(self, data: dict) -> str:
        return file_engine.compress_to_zip(
            data.get("path", "desktop"),
            data.get("name", ""),
            data.get("output_name", "")
        )

    def _handle_extract_archive(self, data: dict) -> str:
        return file_engine.extract_archive(
            data.get("path", "desktop"),
            data.get("name", ""),
            data.get("dest", "") or data.get("destination", "")
        )

    def _handle_get_folder_size(self, data: dict) -> str:
        return file_engine.get_folder_size(
            data.get("path", "desktop"),
            data.get("name", "")
        )

    def _handle_list_folder(self, data: dict) -> str:
        return file_engine.list_folder(
            data.get("path", "desktop"),
            data.get("name", ""),
            bool(data.get("show_hidden", False))
        )

    def _handle_search_files_adv(self, data: dict) -> str:
        return file_engine.search_files(
            query=data.get("query", "*"),
            location=data.get("location", data.get("path", "home")),
            file_type=data.get("file_type", ""),
            min_size_mb=float(data.get("min_size_mb", 0)),
            max_size_mb=float(data.get("max_size_mb", 0)),
            modified_today=bool(data.get("modified_today", False)),
            max_results=int(data.get("max_results", 30)),
        )

    def _handle_find_duplicates(self, data: dict) -> str:
        return file_engine.find_duplicates(
            data.get("path", "desktop"),
            data.get("name", "")
        )

    def _handle_restore_recycle_bin(self, data: dict) -> str:
        return file_engine.restore_recycle_bin()

    def _handle_empty_recycle_bin(self, data: dict) -> str:
        return file_engine.empty_recycle_bin()

    # =========================================================================
    # WINDOW MANAGER HANDLERS
    # =========================================================================

    def _get_window_target(self, data: dict) -> str:
        return data.get("target", "") or data.get("name", "") or data.get("window", "")

    def _handle_minimize_window(self, data: dict) -> str:
        return window_manager.minimize_window(self._get_window_target(data))

    def _handle_maximize_window(self, data: dict) -> str:
        return window_manager.maximize_window(self._get_window_target(data))

    def _handle_restore_window(self, data: dict) -> str:
        return window_manager.restore_window(self._get_window_target(data))

    def _handle_focus_window(self, data: dict) -> str:
        return window_manager.focus_window(self._get_window_target(data))

    def _handle_close_window(self, data: dict) -> str:
        return window_manager.close_window(self._get_window_target(data))

    def _handle_list_windows(self, data: dict) -> str:
        return window_manager.list_open_windows()

    def _handle_snap_window(self, data: dict) -> str:
        target = self._get_window_target(data)
        pos = data.get("position") or data.get("side") or "left"
        return window_manager.snap_window(target, pos)

    def _handle_split_screen(self, data: dict) -> str:
        left = data.get("left_target") or data.get("left") or "vs code"
        right = data.get("right_target") or data.get("right") or "spotify"
        return window_manager.split_screen(left, right)

    def _handle_position_window(self, data: dict) -> str:
        target = self._get_window_target(data)
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        w = int(data.get("width", 960))
        h = int(data.get("height", 1080))
        return window_manager.set_window_geometry(target, x, y, w, h)

    def _handle_launch_workspace_profile(self, data: dict) -> str:
        profile = data.get("profile") or data.get("name") or data.get("target") or "coding"
        return workspace_manager.launch_profile(profile)

    def _handle_move_to_monitor(self, data: dict) -> str:
        target = self._get_window_target(data)
        mon = int(data.get("monitor", data.get("monitor_index", 1)))
        pos = data.get("position", "maximized")
        return workspace_manager.move_to_monitor(target, mon, pos)

    def _handle_tile_all_windows(self, data: dict) -> str:
        return workspace_manager.tile_all_windows()

    def _handle_verify_window_state(self, data: dict) -> str:
        target = self._get_window_target(data)
        ok, msg = workspace_manager.verify_window_state(target, timeout=3.0)
        return msg

    def _handle_execute_workflow(self, data: dict) -> str:
        steps = data.get("steps") or data.get("actions") or []
        if not steps:
            return "No workflow steps provided."
        return workspace_manager.execute_workflow(steps)

    def _handle_restore_browser_session(self, data: dict) -> str:
        from browser_automation import restore_browser_session
        return restore_browser_session()

    # =========================================================================
    # TERMINAL ENGINE HANDLERS
    # =========================================================================

    def _handle_run_terminal(self, data: dict) -> str:
        cmd = data.get("command", "") or data.get("cmd", "") or data.get("target", "")
        cwd = data.get("cwd", "") or data.get("path", "")
        if not cmd:
            raise ValueError("No command specified.")
        shell = data.get("shell", "powershell").lower()
        if shell == "cmd":
            return terminal_engine.run_cmd(cmd, cwd=cwd)
        return terminal_engine.run_powershell(cmd, cwd=cwd)

    def _handle_create_venv(self, data: dict) -> str:
        return terminal_engine.create_venv(
            data.get("path", "desktop"),
            data.get("name", "venv")
        )

    def _handle_install_package(self, data: dict) -> str:
        pkg = data.get("package", "") or data.get("name", "")
        return terminal_engine.install_package(pkg)

    def _handle_run_python(self, data: dict) -> str:
        return terminal_engine.run_python_file(
            data.get("file", "") or data.get("path", ""),
            data.get("args", ""),
            data.get("cwd", "")
        )

    def _handle_kill_process(self, data: dict) -> str:
        name = data.get("name", "") or data.get("target", "")
        return terminal_engine.kill_process(name)

    def _handle_list_processes(self, data: dict) -> str:
        return terminal_engine.list_processes(data.get("filter", "") or data.get("name", ""))

    # =========================================================================
    # SCREEN ENGINE HANDLERS
    # =========================================================================

    def _handle_screenshot(self, data: dict) -> str:
        return screen_engine.take_screenshot(data.get("filename", ""))

    def _handle_screenshot_area(self, data: dict) -> str:
        return screen_engine.take_area_screenshot(
            int(data.get("x", 0)),
            int(data.get("y", 0)),
            int(data.get("width", 800)),
            int(data.get("height", 600)),
            data.get("filename", "")
        )

    def _handle_start_recording(self, data: dict) -> str:
        return screen_engine.start_recording(data.get("filename", ""))

    def _handle_stop_recording(self, data: dict) -> str:
        return screen_engine.stop_recording()

    def _handle_ocr_screen(self, data: dict) -> str:
        region = None
        if all(k in data for k in ("x", "y", "width", "height")):
            region = (int(data["x"]), int(data["y"]), int(data["width"]), int(data["height"]))
        return screen_engine.ocr_screen(region)

    # =========================================================================
    # CLIPBOARD ENGINE HANDLERS
    # =========================================================================

    def _handle_read_clipboard(self, data: dict) -> str:
        return clipboard_engine.read()

    def _handle_write_clipboard(self, data: dict) -> str:
        text = data.get("text", "") or data.get("content", "")
        return clipboard_engine.write(text)

    def _handle_clear_clipboard(self, data: dict) -> str:
        return clipboard_engine.clear()

    def _handle_clipboard_history(self, data: dict) -> str:
        history = clipboard_engine.get_history()
        if not history:
            return "Clipboard history is empty."
        lines = [f"  {i+1}. {h[:80]}" for i, h in enumerate(reversed(history))]
        return "Clipboard history (most recent first):\n" + "\n".join(lines)

    # =========================================================================
    # PREFERENCE / MEMORY HANDLERS
    # =========================================================================

    def _handle_remember_preference(self, data: dict) -> str:
        from memory import preference_store
        key   = data.get("key", "") or data.get("name", "")
        value = data.get("value", "") or data.get("content", "")
        return preference_store.remember(key, value)

    def _handle_forget_preference(self, data: dict) -> str:
        from memory import preference_store
        key = data.get("key", "") or data.get("name", "")
        return preference_store.forget(key)

    def _handle_remember_folder(self, data: dict) -> str:
        from memory import preference_store
        label = data.get("label", "") or data.get("name", "")
        path  = data.get("path", "") or data.get("folder", "")
        return preference_store.remember_folder(label, path)

    def _handle_show_preferences(self, data: dict) -> str:
        from memory import preference_store
        prefs   = preference_store.get_all()
        folders = preference_store.get_all_folders()
        if not prefs and not folders:
            return "No preferences stored yet. Say 'remember [something]' to save one."
        lines = []
        if prefs:
            lines.append("Preferences:")
            for k, v in prefs.items():
                lines.append(f"  {k}: {v}")
        if folders:
            lines.append("Bookmarked folders:")
            for k, v in folders.items():
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)


# Global Singleton Windows Automation Engine
automation_engine = WindowsAutomationEngine()


def extract_action_intent(llm_response_text: str) -> dict | None:
    """Extract structured JSON action payload or multi-step workflow array from LLM markdown completion."""
    if not llm_response_text:
        return None

    # Check for all ```json ... ``` blocks
    json_blocks = re.findall(r"```json\s*([\s\S]*?)\s*```", llm_response_text, re.IGNORECASE)
    extracted_actions = []

    for block in json_blocks:
        try:
            data = json.loads(block.strip())
            if isinstance(data, list):
                valid_steps = [item for item in data if isinstance(item, dict) and "action" in item]
                extracted_actions.extend(valid_steps)
            elif isinstance(data, dict) and "action" in data:
                if data["action"] == "execute_workflow" and "steps" in data:
                    return data
                extracted_actions.append(data)
        except Exception:
            pass

    if len(extracted_actions) == 1:
        return extracted_actions[0]
    elif len(extracted_actions) > 1:
        return {"action": "execute_workflow", "steps": extracted_actions}

    # Inline single JSON fallback
    inline_match = re.search(r"\{\s*\"action\"\s*:\s*\"[^\"]+\"[\s\S]*?\}", llm_response_text)
    if inline_match:
        try:
            data = json.loads(inline_match.group(0).strip())
            if isinstance(data, dict) and "action" in data:
                return data
        except Exception:
            pass

    return None
