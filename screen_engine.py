"""
IRIS AI - Screen Engine
Screenshot, screen recording, and OCR text extraction.
Uses pyautogui/PIL (primary), PowerShell fallback for screenshots.
OCR via pytesseract with graceful fallback.
"""

import os
import datetime
import subprocess
import threading
from pathlib import Path
from rich.console import Console
from debug_logger import debug_log, log_exception

console = Console()

SCREENSHOTS_DIR = Path.home() / "Pictures" / "Screenshots"
RECORDINGS_DIR  = Path.home() / "Videos" / "IRIS Recordings"

# ── Optional libs ─────────────────────────────────────────────────

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None
    HAS_PYAUTOGUI = False

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    Image = None
    ImageGrab = None
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    pytesseract = None
    HAS_TESSERACT = False


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


class ScreenEngine:

    def __init__(self):
        self._recording_proc = None
        self._recording_path = None

    # ── Screenshots ───────────────────────────────────────────────

    def take_screenshot(self, filename: str = "") -> str:
        """Capture the full screen and save to Pictures/Screenshots."""
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        fname    = filename or f"IRIS_{_timestamp()}.png"
        filepath = SCREENSHOTS_DIR / fname

        # Method 1: pyautogui
        if HAS_PYAUTOGUI:
            try:
                img = pyautogui.screenshot()
                img.save(filepath)
                return f"Screenshot saved: {filepath}"
            except Exception:
                pass

        # Method 2: PIL ImageGrab
        if HAS_PIL:
            try:
                img = ImageGrab.grab()
                img.save(filepath)
                return f"Screenshot saved: {filepath}"
            except Exception:
                pass

        # Method 3: PowerShell
        try:
            ps_cmd = (
                "[Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null;"
                "[Reflection.Assembly]::LoadWithPartialName('System.Drawing') | Out-Null;"
                "$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
                "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height;"
                "$g = [System.Drawing.Graphics]::FromImage($bmp);"
                "$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size);"
                f"$bmp.Save('{filepath}');"
                "$g.Dispose(); $bmp.Dispose()"
            )
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                capture_output=True, timeout=15
            )
            if filepath.exists():
                return f"Screenshot saved: {filepath}"
        except Exception as ex:
            log_exception(ex, context="SCREENSHOT_PS")

        return "Could not capture screenshot. Install Pillow: pip install Pillow"

    def take_area_screenshot(self, x: int = 0, y: int = 0, w: int = 800, h: int = 600, filename: str = "") -> str:
        """Capture a specific screen region."""
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        fname    = filename or f"IRIS_Area_{_timestamp()}.png"
        filepath = SCREENSHOTS_DIR / fname

        if HAS_PIL:
            try:
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                img.save(filepath)
                return f"Area screenshot saved: {filepath}"
            except Exception as ex:
                return f"Area capture failed: {ex}"

        if HAS_PYAUTOGUI:
            try:
                img = pyautogui.screenshot(region=(x, y, w, h))
                img.save(filepath)
                return f"Area screenshot saved: {filepath}"
            except Exception as ex:
                return f"Area capture failed: {ex}"

        return "Area screenshot requires Pillow: pip install Pillow"

    # ── Screen Recording ──────────────────────────────────────────

    def start_recording(self, filename: str = "") -> str:
        """Start screen recording via ffmpeg (if available) or PowerShell."""
        if self._recording_proc:
            return "Already recording. Stop the current recording first."

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        fname = filename or f"IRIS_Recording_{_timestamp()}.mp4"
        self._recording_path = RECORDINGS_DIR / fname

        # Try ffmpeg
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
            cmd = [
                "ffmpeg", "-y",
                "-f", "gdigrab", "-framerate", "30", "-i", "desktop",
                "-c:v", "libx264", "-preset", "ultrafast",
                str(self._recording_path)
            ]
            self._recording_proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return f"Recording started: {self._recording_path}\nSay 'stop recording' to finish."
        except FileNotFoundError:
            self._recording_path = None
            return (
                "ffmpeg not found. Install it for screen recording:\n"
                "  winget install ffmpeg\n"
                "or download from https://ffmpeg.org/download.html"
            )
        except Exception as ex:
            self._recording_path = None
            return f"Could not start recording: {ex}"

    def stop_recording(self) -> str:
        """Stop the current screen recording."""
        if not self._recording_proc:
            return "No recording is currently active."
        try:
            self._recording_proc.stdin.write(b"q")
            self._recording_proc.stdin.flush()
            self._recording_proc.wait(timeout=10)
        except Exception:
            try:
                self._recording_proc.terminate()
            except Exception:
                pass
        path = self._recording_path
        self._recording_proc = None
        self._recording_path = None
        return f"Recording saved: {path}"

    # ── OCR ───────────────────────────────────────────────────────

    def ocr_screen(self, region: tuple = None) -> str:
        """
        Extract text from the screen via OCR.
        region: (x, y, width, height) or None for full screen.
        """
        if not HAS_TESSERACT:
            return (
                "OCR requires pytesseract and Tesseract OCR engine.\n"
                "Install: pip install pytesseract Pillow\n"
                "Then install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki"
            )
        if not HAS_PIL:
            return "OCR requires Pillow: pip install Pillow"

        try:
            if region:
                x, y, w, h = region
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            else:
                img = ImageGrab.grab()

            text = pytesseract.image_to_string(img).strip()
            if not text:
                return "No text found on screen."
            if len(text) > 2000:
                text = text[:2000] + "\n... [truncated]"
            return f"Text found on screen:\n{text}"
        except Exception as ex:
            log_exception(ex, context="OCR")
            return f"OCR failed: {ex}"

    def ocr_image_file(self, filepath: str) -> str:
        """Extract text from an image file."""
        if not HAS_TESSERACT or not HAS_PIL:
            return "OCR requires pytesseract and Pillow: pip install pytesseract Pillow"
        try:
            img  = Image.open(filepath)
            text = pytesseract.image_to_string(img).strip()
            return f"Text extracted:\n{text}" if text else "No text found in image."
        except Exception as ex:
            return f"OCR failed: {ex}"


# Global Singleton
screen_engine = ScreenEngine()
