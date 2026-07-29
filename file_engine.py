"""
IRIS AI - Advanced File & Folder Engine
Handles ZIP compression, duplicate detection, advanced search,
batch folder creation, recycle bin, and file content editing.
"""

import os
import re
import sys
import math
import time
import shutil
import hashlib
import zipfile
import fnmatch
import datetime
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import box

from debug_logger import debug_log, log_exception

console = Console()

# ── Path keyword resolver ─────────────────────────────────────────

KNOWN_LOCATIONS = {
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
    "temp":          Path(os.environ.get("TEMP", Path.home() / "AppData/Local/Temp")),
    "appdata":       Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")),
    "localappdata":  Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")),
    "onedrive":      Path.home() / "OneDrive",
    "onedrive desktop": Path.home() / "OneDrive" / "Desktop",
}

# Support OneDrive Desktop (common on modern Windows)
_onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
if _onedrive_desktop.exists():
    KNOWN_LOCATIONS["desktop"] = _onedrive_desktop

def resolve_path(raw: str, name: str = "") -> Path:
    """Resolve keyword location string to real Windows path."""
    if not raw:
        return KNOWN_LOCATIONS["desktop"]

    key = raw.strip().lower()

    if key in KNOWN_LOCATIONS:
        base = KNOWN_LOCATIONS[key]
        return (base / name) if name else base

    for kw, folder in KNOWN_LOCATIONS.items():
        if key.startswith(kw + "/") or key.startswith(kw + "\\"):
            rest = raw[len(kw):].lstrip("\\/")
            return folder / rest

    p = Path(raw).expanduser()
    if p.is_absolute():
        return (p / name) if name else p.resolve()

    # Relative path — treat as Desktop-relative
    return (KNOWN_LOCATIONS["desktop"] / raw / name).resolve() if name else (KNOWN_LOCATIONS["desktop"] / raw).resolve()


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        size_bytes /= 1024.0
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} PB"


# ── File Template Generator ───────────────────────────────────────

FILE_TEMPLATES = {
    ".md":   "# {name}\n\n",
    ".py":   '"""\n{name}\n"""\n\n\ndef main():\n    pass\n\n\nif __name__ == "__main__":\n    main()\n',
    ".html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <title>{name}</title>\n</head>\n<body>\n\n</body>\n</html>\n",
    ".css":  "/* {name} */\n\n",
    ".js":   "// {name}\n\n",
    ".json": "{}\n",
    ".csv":  "column1,column2,column3\n",
    ".java": "public class {classname} {{\n    public static void main(String[] args) {{\n        System.out.println(\"Hello, World!\");\n    }}\n}}\n",
    ".cpp":  '#include <iostream>\nusing namespace std;\n\nint main() {{\n    cout << "Hello, World!" << endl;\n    return 0;\n}}\n',
    ".c":    '#include <stdio.h>\n\nint main() {{\n    printf("Hello, World!\\n");\n    return 0;\n}}\n',
    ".ts":   "// {name}\n\n",
    ".rs":   'fn main() {{\n    println!("Hello, World!");\n}}\n',
    ".go":   'package main\n\nimport "fmt"\n\nfunc main() {{\n    fmt.Println("Hello, World!")\n}}\n',
    ".sh":   "#!/bin/bash\n# {name}\n\n",
    ".bat":  "@echo off\nREM {name}\n\n",
    ".xml":  '<?xml version="1.0" encoding="UTF-8"?>\n<root>\n</root>\n',
    ".yaml": "# {name}\n\n",
    ".yml":  "# {name}\n\n",
    ".toml": "# {name}\n\n",
    ".ini":  "; {name}\n\n",
    ".env":  "# {name} environment variables\n\n",
    ".sql":  "-- {name}\n\n",
    ".r":    "# {name}\n\n",
    ".txt":  "",
}

def get_file_template(filename: str, content: str = "") -> str:
    """Return appropriate starter content for a new file."""
    if content:
        return content
    ext  = Path(filename).suffix.lower()
    name = Path(filename).stem
    tmpl = FILE_TEMPLATES.get(ext, "")
    classname = re.sub(r"[^a-zA-Z0-9]", "", name).capitalize() or "Main"
    return tmpl.format(name=name, classname=classname)


# ── Core File Engine Class ────────────────────────────────────────

class FileEngine:

    # ── CREATE ────────────────────────────────────────────────────

    def create_file(self, path: str, name: str = "", content: str = "") -> str:
        p = resolve_path(path, name)
        if p.suffix == "" and not name:
            raise ValueError("Please include a filename with extension (e.g. notes.txt).")
        p.parent.mkdir(parents=True, exist_ok=True)
        starter = get_file_template(p.name, content)
        p.write_text(starter, encoding="utf-8")
        return f"Created {p.name} at: {p}"

    def create_folder(self, path: str, name: str = "") -> str:
        p = resolve_path(path, name)
        p.mkdir(parents=True, exist_ok=True)
        return f"Created folder: {p}"

    def create_batch_folders(self, path: str, prefix: str, start: int, end: int) -> str:
        """Create numbered folders — e.g. Day1 to Day10."""
        base = resolve_path(path)
        base.mkdir(parents=True, exist_ok=True)
        created = []
        for i in range(start, end + 1):
            folder_name = f"{prefix}{i}"
            (base / folder_name).mkdir(exist_ok=True)
            created.append(folder_name)
        return f"Created {len(created)} folders ({prefix}{start}–{prefix}{end}) in: {base}"

    # ── READ ──────────────────────────────────────────────────────

    def read_file(self, path: str, name: str = "", max_lines: int = 100) -> str:
        p = resolve_path(path, name)
        if not p.exists():
            return f"File not found: {p}"
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            total = len(lines)
            shown = lines[:max_lines]
            text  = "\n".join(f"{i+1:4}: {ln}" for i, ln in enumerate(shown))
            suffix = f"\n\n... ({total - max_lines} more lines not shown)" if total > max_lines else ""
            return f"=== {p.name} ({total} lines) ===\n{text}{suffix}"
        except Exception as ex:
            return f"Cannot read file: {ex}"

    def append_to_file(self, path: str, name: str, text: str) -> str:
        p = resolve_path(path, name)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        with p.open("a", encoding="utf-8") as f:
            f.write(("\n" if not text.startswith("\n") else "") + text)
        return f"Appended {len(text)} characters to: {p.name}"

    def replace_line(self, path: str, name: str, line_number: int, new_text: str) -> str:
        p = resolve_path(path, name)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        if line_number < 1 or line_number > len(lines):
            raise ValueError(f"Line {line_number} out of range (file has {len(lines)} lines).")
        old = lines[line_number - 1].rstrip("\n\r")
        lines[line_number - 1] = new_text + "\n"
        p.write_text("".join(lines), encoding="utf-8")
        return f"Line {line_number} replaced:\n  Before: {old}\n  After:  {new_text}"

    def delete_line(self, path: str, name: str, line_number: int) -> str:
        p = resolve_path(path, name)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        if line_number < 1 or line_number > len(lines):
            raise ValueError(f"Line {line_number} out of range.")
        removed = lines.pop(line_number - 1).strip()
        p.write_text("".join(lines), encoding="utf-8")
        return f"Deleted line {line_number}: \"{removed[:80]}\""

    def search_in_file(self, path: str, name: str, query: str) -> str:
        p = resolve_path(path, name)
        if not p.exists():
            return f"File not found: {p}"
        lines   = p.read_text(encoding="utf-8", errors="replace").splitlines()
        matches = [(i + 1, ln) for i, ln in enumerate(lines) if query.lower() in ln.lower()]
        if not matches:
            return f"No matches for '{query}' in {p.name}"
        result = "\n".join(f"  Line {n:4}: {ln.strip()}" for n, ln in matches[:30])
        more   = f"\n  ... and {len(matches) - 30} more matches" if len(matches) > 30 else ""
        return f"Found {len(matches)} occurrence(s) of '{query}' in {p.name}:\n{result}{more}"

    # ── COMPRESS / EXTRACT ────────────────────────────────────────

    def compress_to_zip(self, path: str, name: str = "", output_name: str = "") -> str:
        p = resolve_path(path, name)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {p}")
        out_name = output_name or (p.name + ".zip")
        out_path = p.parent / out_name
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if p.is_dir():
                for file in p.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(p.parent))
            else:
                zf.write(p, p.name)
        size = _human_size(out_path.stat().st_size)
        return f"Compressed to: {out_path} ({size})"

    def extract_archive(self, path: str, name: str = "", dest: str = "") -> str:
        p = resolve_path(path, name)
        if not p.exists():
            raise FileNotFoundError(f"Archive not found: {p}")
        dest_p = resolve_path(dest) if dest else p.parent
        dest_p.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p, "r") as zf:
                zf.extractall(dest_p)
        else:
            shutil.unpack_archive(str(p), str(dest_p))
        return f"Extracted to: {dest_p}"

    # ── SIZE & LISTING ────────────────────────────────────────────

    def get_folder_size(self, path: str, name: str = "") -> str:
        p = resolve_path(path, name)
        if not p.exists():
            return f"Path not found: {p}"
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        count = sum(1 for _ in p.rglob("*") if _.is_file())
        return f"{p.name}: {_human_size(total)} ({count:,} files)"

    def list_folder(self, path: str, name: str = "", show_hidden: bool = False) -> str:
        p = resolve_path(path, name)
        if not p.exists():
            return f"Folder not found: {p}"
        items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        if not show_hidden:
            items = [i for i in items if not i.name.startswith(".")]
        if not items:
            return f"Folder is empty: {p}"
        lines = []
        for item in items[:50]:
            if item.is_dir():
                lines.append(f"  📁 {item.name}/")
            else:
                lines.append(f"  📄 {item.name}  ({_human_size(item.stat().st_size)})")
        more = f"\n  ... and {len(items) - 50} more items" if len(items) > 50 else ""
        return f"Contents of {p.name} ({len(items)} items):\n" + "\n".join(lines) + more

    # ── ADVANCED SEARCH ───────────────────────────────────────────

    def search_files(
        self,
        query: str = "*",
        location: str = "home",
        file_type: str = "",
        min_size_mb: float = 0,
        max_size_mb: float = 0,
        modified_today: bool = False,
        max_results: int = 30,
    ) -> str:
        root  = resolve_path(location)
        matches = []
        now   = datetime.datetime.now()
        today = now.date()

        try:
            for f in root.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    # Type filter
                    if file_type and not f.suffix.lower().lstrip(".") == file_type.lower().lstrip("."):
                        continue
                    # Name filter
                    if query and query != "*" and query.lower() not in f.name.lower():
                        continue
                    st = f.stat()
                    size_mb = st.st_size / (1024 * 1024)
                    # Size filters
                    if min_size_mb > 0 and size_mb < min_size_mb:
                        continue
                    if max_size_mb > 0 and size_mb > max_size_mb:
                        continue
                    # Date filter
                    if modified_today:
                        mdate = datetime.datetime.fromtimestamp(st.st_mtime).date()
                        if mdate != today:
                            continue
                    matches.append((f, st.st_size))
                    if len(matches) >= max_results:
                        break
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass

        if not matches:
            return f"No files found matching your criteria in {root}"

        lines = [f"  • {f.name}  ({_human_size(s)}) — {f.parent}" for f, s in matches]
        return f"Found {len(matches)} file(s):\n" + "\n".join(lines)

    # ── DUPLICATE FINDER ──────────────────────────────────────────

    def find_duplicates(self, path: str, name: str = "") -> str:
        root = resolve_path(path, name)
        if not root.exists():
            return f"Folder not found: {root}"

        hash_map: dict[str, list[Path]] = {}
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            try:
                h = hashlib.md5(f.read_bytes()).hexdigest()
                hash_map.setdefault(h, []).append(f)
            except (PermissionError, OSError):
                continue

        dupes = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
        if not dupes:
            return f"No duplicate files found in {root}"

        lines = []
        total_wasted = 0
        for paths in list(dupes.values())[:20]:
            size = paths[0].stat().st_size
            wasted = size * (len(paths) - 1)
            total_wasted += wasted
            lines.append(f"  [{_human_size(size)} each × {len(paths)}]")
            for p in paths:
                lines.append(f"    → {p}")
        return (
            f"Found {len(dupes)} duplicate group(s). "
            f"Wasted space: {_human_size(total_wasted)}\n" + "\n".join(lines)
        )

    # ── RECYCLE BIN ───────────────────────────────────────────────

    def restore_recycle_bin(self) -> str:
        """Open Recycle Bin in Explorer for manual restore."""
        try:
            subprocess.Popen(["explorer.exe", "shell:RecycleBinFolder"])
            return "Opened Recycle Bin in File Explorer. Select items and use Restore to recover them."
        except Exception as ex:
            return f"Could not open Recycle Bin: {ex}"

    def empty_recycle_bin(self) -> str:
        """Empty the Windows Recycle Bin via PowerShell."""
        try:
            subprocess.run(
                ["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=15
            )
            return "Recycle Bin emptied successfully."
        except Exception as ex:
            return f"Could not empty Recycle Bin: {ex}"

    # ── RENAME / COPY / MOVE ─────────────────────────────────────

    def rename_item(self, path: str, name: str, new_name: str) -> str:
        p = resolve_path(path, name)
        if not p.exists():
            # Try Desktop as fallback
            p = resolve_path("desktop", name)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {name} in {path}")
        dst = p.parent / new_name
        p.rename(dst)
        return f"Renamed '{p.name}' → '{dst.name}'"

    def copy_item(self, src_path: str, src_name: str, dst_path: str, dst_name: str = "") -> str:
        src = resolve_path(src_path, src_name)
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        dst_dir = resolve_path(dst_path)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / (dst_name or src.name)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return f"Copied '{src.name}' → {dst}"

    def move_item(self, src_path: str, src_name: str, dst_path: str) -> str:
        src = resolve_path(src_path, src_name)
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        dst_dir = resolve_path(dst_path)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        shutil.move(str(src), str(dst))
        return f"Moved '{src.name}' → {dst}"

    def delete_item(self, path: str, name: str = "") -> str:
        p = resolve_path(path, name)
        if not p.exists():
            fallback = resolve_path("desktop", name or path)
            if fallback.exists():
                p = fallback
            else:
                return f"Not found: {p}"
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"Deleted: {p}"


# Global Singleton
file_engine = FileEngine()
