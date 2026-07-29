"""
IRIS AI - Terminal Engine
Controlled execution of PowerShell, CMD, Git Bash commands.
Virtual environment creation, package installation, process management.
"""

import os
import re
import sys
import time
import subprocess
import threading
from pathlib import Path
from typing import Optional
from rich.console import Console
from debug_logger import debug_log, log_exception

console = Console()

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

# Max characters of terminal output shown to user
MAX_OUTPUT_CHARS = 2000


class TerminalEngine:

    def __init__(self):
        self._last_output = ""
        self._last_command = ""

    # ── Command Execution ─────────────────────────────────────────

    def run_powershell(self, command: str, timeout: int = 30, cwd: str = "") -> str:
        """Run a PowerShell command and capture output."""
        self._last_command = command
        kwargs = {"capture_output": True, "text": True, "timeout": timeout}
        if cwd:
            kwargs["cwd"] = cwd

        try:
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", command],
                **kwargs
            )
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            combined = (out + ("\n[STDERR] " + err if err else "")).strip()
            self._last_output = combined

            if not combined:
                return f"Command completed successfully (exit code {result.returncode})."

            # Truncate very long output
            if len(combined) > MAX_OUTPUT_CHARS:
                combined = combined[:MAX_OUTPUT_CHARS] + f"\n... [output truncated, {len(combined)} total chars]"

            return f"PowerShell output:\n{combined}"
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s."
        except FileNotFoundError:
            return "PowerShell not found on this system."
        except Exception as ex:
            log_exception(ex, context="TERMINAL_PS")
            return f"Error running command: {ex}"

    def run_cmd(self, command: str, timeout: int = 30, cwd: str = "") -> str:
        """Run a CMD command and capture output."""
        self._last_command = command
        kwargs = {"capture_output": True, "text": True, "timeout": timeout, "shell": True}
        if cwd:
            kwargs["cwd"] = cwd

        try:
            result = subprocess.run(command, **kwargs)
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            combined = (out + ("\n" + err if err else "")).strip()
            self._last_output = combined

            if not combined:
                return f"Command completed (exit code {result.returncode})."
            if len(combined) > MAX_OUTPUT_CHARS:
                combined = combined[:MAX_OUTPUT_CHARS] + "\n... [truncated]"
            return f"Output:\n{combined}"
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s."
        except Exception as ex:
            return f"Error: {ex}"

    def run_git(self, args: str, cwd: str = "") -> str:
        """Run a git command."""
        full_cmd = f"git {args}"
        return self.run_cmd(full_cmd, cwd=cwd or str(Path.cwd()))

    def get_last_output(self) -> str:
        return self._last_output or "No previous command output."

    # ── Python / Pip ──────────────────────────────────────────────

    def install_package(self, package: str) -> str:
        """Install a Python package via pip."""
        cmd = f'"{sys.executable}" -m pip install {package} --quiet'
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True, text=True, timeout=120
            )
            out = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                return f"Successfully installed: {package}"
            return f"pip install failed:\n{out[:1000]}"
        except subprocess.TimeoutExpired:
            return "Package install timed out (>120s). Check your internet connection."
        except Exception as ex:
            return f"Error: {ex}"

    def run_python_file(self, filepath: str, args: str = "", cwd: str = "") -> str:
        """Run a Python file."""
        p = Path(filepath).expanduser().resolve()
        if not p.exists():
            return f"File not found: {p}"
        cmd_list = [sys.executable, str(p)] + (args.split() if args else [])
        try:
            result = subprocess.run(
                cmd_list, capture_output=True, text=True, timeout=30,
                cwd=cwd or str(p.parent)
            )
            out = (result.stdout + result.stderr).strip()
            if len(out) > MAX_OUTPUT_CHARS:
                out = out[:MAX_OUTPUT_CHARS] + "\n... [truncated]"
            return f"Output:\n{out}" if out else "Script completed with no output."
        except subprocess.TimeoutExpired:
            return "Script timed out after 30s."
        except Exception as ex:
            return f"Error running script: {ex}"

    # ── Virtual Environments ──────────────────────────────────────

    def create_venv(self, path: str, name: str = "venv") -> str:
        """Create a Python virtual environment."""
        from file_engine import resolve_path
        base = resolve_path(path)
        venv_path = base / name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                activate = venv_path / "Scripts" / "activate"
                return (
                    f"Virtual environment created: {venv_path}\n"
                    f"Activate with: {activate}"
                )
            return f"venv creation failed:\n{result.stderr.strip()[:500]}"
        except Exception as ex:
            return f"Error creating venv: {ex}"

    # ── Process Management ────────────────────────────────────────

    def list_processes(self, filter_name: str = "") -> str:
        """List running processes, optionally filtered."""
        if HAS_PSUTIL:
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
                try:
                    info = p.info
                    if filter_name and filter_name.lower() not in info["name"].lower():
                        continue
                    mem_mb = info["memory_info"].rss / (1024 * 1024) if info["memory_info"] else 0
                    procs.append(f"  {info['pid']:6}  {info['name']:<30} {mem_mb:.1f} MB")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if not procs:
                return f"No processes found matching '{filter_name}'." if filter_name else "No processes found."
            header = f"{'PID':>6}  {'Name':<30} Memory"
            return f"{header}\n" + "\n".join(procs[:30])

        out = self.run_cmd(f'tasklist | findstr /i "{filter_name}"' if filter_name else "tasklist")
        return out

    def kill_process(self, name: str) -> str:
        """Kill a process by name (requires confirmation — handled at engine level)."""
        if HAS_PSUTIL:
            killed = 0
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if name.lower() in proc.info["name"].lower():
                        proc.terminate()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return f"Terminated {killed} process(es) matching '{name}'." if killed else f"No process found: '{name}'."

        result = subprocess.run(
            ["taskkill", "/f", "/im", f"{name}.exe"],
            capture_output=True, text=True
        )
        return result.stdout.strip() or result.stderr.strip()


# Global Singleton
terminal_engine = TerminalEngine()
