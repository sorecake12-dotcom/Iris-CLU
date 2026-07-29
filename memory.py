"""
IRIS AI - Persistent Memory Store
Saves and restores cross-session conversation history.
Stored in config/memory.json — excluded from Git via .gitignore.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

CONFIG_DIR        = Path(__file__).parent / "config"
MEMORY_FILE       = CONFIG_DIR / "memory.json"
PREFERENCES_FILE  = CONFIG_DIR / "preferences.json"

# Max exchanges kept in memory file (older ones are summarized)
MAX_FULL_ENTRIES   = 200   # total raw exchanges stored on disk
MAX_CONTEXT_INJECT = 10    # number of recent exchanges injected into LLM context at startup


class MemoryStore:
    """
    Persistent cross-session memory for IRIS AI.
    Stores conversation history as a flat list of {role, content, ts} entries.
    """

    def __init__(self):
        self._entries: list[dict] = []
        self._loaded = False

    # ── I/O ──────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        """Load all stored memory entries from disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if MEMORY_FILE.exists():
                data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _save(self, entries: list[dict]):
        """Persist memory entries to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            MEMORY_FILE.write_text(
                json.dumps(entries, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as ex:
            console.print(f"[bold red][MEMORY] Failed to save: {ex}[/bold red]")

    # ── Public API ────────────────────────────────────────────────

    def load_recent(self, n: int = MAX_CONTEXT_INJECT) -> list[dict]:
        """
        Load the N most recent exchanges from disk.
        Returns a list of {role, content} dicts compatible with Groq chat history format.
        """
        entries = self._load()
        self._loaded = True
        # Strip timestamps for LLM injection
        recent = entries[-n:] if len(entries) > n else entries
        return [{"role": e["role"], "content": e["content"]} for e in recent]

    def save_session(self, chat_history: list[dict]):
        """
        Append a session's chat history to persistent memory.
        Trims old entries if total exceeds MAX_FULL_ENTRIES.
        """
        if not chat_history:
            return

        existing = self._load()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_entries = [
            {"role": e["role"], "content": e["content"], "ts": ts}
            for e in chat_history
            if e.get("role") in ("user", "assistant") and e.get("content", "").strip()
        ]

        combined = existing + new_entries

        # Trim to MAX_FULL_ENTRIES — keep newest
        if len(combined) > MAX_FULL_ENTRIES:
            combined = combined[-MAX_FULL_ENTRIES:]

        self._save(combined)

    def clear(self):
        """Delete all stored memory."""
        try:
            if MEMORY_FILE.exists():
                MEMORY_FILE.unlink()
            console.print("[bold yellow]  [MEM] All conversation memory cleared.[/bold yellow]\n")
        except Exception as ex:
            console.print(f"[bold red][MEMORY] Failed to clear: {ex}[/bold red]")

    def get_stats(self) -> dict:
        """Return memory statistics for display."""
        entries = self._load()
        if not entries:
            return {"total": 0, "first": None, "last": None, "size_kb": 0}

        first_ts = entries[0].get("ts", "unknown")
        last_ts  = entries[-1].get("ts", "unknown")
        size_kb  = round(MEMORY_FILE.stat().st_size / 1024, 1) if MEMORY_FILE.exists() else 0

        return {
            "total":    len(entries),
            "first":    first_ts,
            "last":     last_ts,
            "size_kb":  size_kb,
        }

    def print_status(self, theme_key: str = "emerald"):
        """Print a Rich panel showing memory stats and recent entries."""
        import config as cfg_mod
        t = cfg_mod.THEMES.get(theme_key, cfg_mod.THEMES[cfg_mod.DEFAULT_THEME])

        stats   = self.get_stats()
        entries = self._load()

        if not entries:
            console.print("[dim yellow]  [MEM] No memory stored yet. IRIS will remember your conversations after each session.[/dim yellow]\n")
            return

        # Stats table
        table = Table(
            title="[bold cyan][::] IRIS PERSISTENT MEMORY [::][/bold cyan]",
            border_style=t["border"],
            box=box.ROUNDED
        )
        table.add_column("Metric",  style=f"bold {t['accent']}", no_wrap=True)
        table.add_column("Value",   style="white")

        table.add_row("Total exchanges stored", str(stats["total"]))
        table.add_row("Oldest entry",           stats["first"] or "—")
        table.add_row("Newest entry",           stats["last"]  or "—")
        table.add_row("Memory file size",       f"{stats['size_kb']} KB")
        table.add_row("Storage location",       str(MEMORY_FILE))

        console.print()
        console.print(table)

        # Show last 5 exchanges preview
        if entries:
            console.print(f"\n[dim cyan]  Last {min(5, len(entries))} stored exchanges:[/dim cyan]")
            for entry in entries[-5:]:
                role_label = "[bold cyan]IRIS[/bold cyan]" if entry["role"] == "assistant" else "[bold white]Boss[/bold white]"
                preview = entry["content"][:80].replace("\n", " ")
                ts = entry.get("ts", "")
                console.print(f"  [{ts}] {role_label}: {preview}{'...' if len(entry['content']) > 80 else ''}")

        console.print(f"\n[dim]  Run  /clearmemory  to wipe all stored memory.[/dim]\n")


# ── Global Singleton ──────────────────────────────────────────────
memory_store = MemoryStore()


# ─────────────────────────────────────────────────────────────────
# Preference Memory — persistent key/value store for user prefs
# ─────────────────────────────────────────────────────────────────

class PreferenceStore:
    """
    Stores user preferences and bookmarked folders across sessions.
    Saved to config/preferences.json (git-ignored).

    Examples:
        remember("favorite_editor", "VS Code")
        remember_folder("projects", "C:/Projects")
    """

    def _load(self) -> dict:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if PREFERENCES_FILE.exists():
                data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {"prefs": {}, "folders": {}}

    def _save(self, data: dict):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            PREFERENCES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as ex:
            console.print(f"[bold red][PREFS] Save failed: {ex}[/bold red]")

    # ── Preferences ───────────────────────────────────────────────

    def remember(self, key: str, value: str) -> str:
        data = self._load()
        data.setdefault("prefs", {})[key.strip().lower()] = value.strip()
        self._save(data)
        return f"Got it, Boss! I'll remember that {key} = {value}."

    def forget(self, key: str) -> str:
        data = self._load()
        k = key.strip().lower()
        if k in data.get("prefs", {}):
            del data["prefs"][k]
            self._save(data)
            return f"Forgotten: {key}."
        return f"I don't have '{key}' stored."

    def get(self, key: str) -> str | None:
        return self._load().get("prefs", {}).get(key.strip().lower())

    def get_all(self) -> dict:
        return self._load().get("prefs", {})

    # ── Folder Bookmarks ──────────────────────────────────────────

    def remember_folder(self, label: str, path: str) -> str:
        data = self._load()
        data.setdefault("folders", {})[label.strip().lower()] = path.strip()
        self._save(data)
        return f"Bookmarked folder '{label}' → {path}"

    def get_folder(self, label: str) -> str | None:
        return self._load().get("folders", {}).get(label.strip().lower())

    def forget_folder(self, label: str) -> str:
        data = self._load()
        k = label.strip().lower()
        if k in data.get("folders", {}):
            del data["folders"][k]
            self._save(data)
            return f"Removed folder bookmark: {label}."
        return f"No bookmark found for '{label}'."

    def get_all_folders(self) -> dict:
        return self._load().get("folders", {})

    # ── Display ───────────────────────────────────────────────────

    def print_all(self, theme_key: str = "emerald"):
        import config
        t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])
        data    = self._load()
        prefs   = data.get("prefs", {})
        folders = data.get("folders", {})

        if not prefs and not folders:
            console.print("[dim yellow]  No preferences stored yet. Say 'remember my theme is cyberpunk' to save one.[/dim yellow]\n")
            return

        if prefs:
            table = Table(
                title="[bold cyan][::] STORED PREFERENCES [::][/bold cyan]",
                border_style=t["border"], box=box.ROUNDED
            )
            table.add_column("Key",   style=f"bold {t['accent']}")
            table.add_column("Value", style="white")
            for k, v in prefs.items():
                table.add_row(k, str(v))
            console.print()
            console.print(table)

        if folders:
            ftable = Table(
                title="[bold cyan][::] BOOKMARKED FOLDERS [::][/bold cyan]",
                border_style=t["border"], box=box.ROUNDED
            )
            ftable.add_column("Label",  style=f"bold {t['accent']}")
            ftable.add_column("Path",   style="white")
            for k, v in folders.items():
                ftable.add_row(k, str(v))
            console.print()
            console.print(ftable)

        console.print(f"[dim]  Say 'forget [key]' to remove a preference.[/dim]\n")


# Global Singleton
preference_store = PreferenceStore()
