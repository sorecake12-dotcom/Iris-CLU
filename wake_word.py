"""
IRIS AI - Wake Word Detection Engine
Listens in the background for "Hey IRIS" or "IRIS" and triggers command input.
Uses SpeechRecognition + pyaudio. Gracefully disabled if no microphone or libs are missing.
"""

import os
import sys
import time
import threading
from rich.console import Console
from debug_logger import debug_log, log_exception

console = Console()

# ── Optional dependencies ─────────────────────────────────────────
try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    sr = None
    HAS_SR = False

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    pyaudio = None
    HAS_PYAUDIO = False

WAKE_PHRASES = [
    "hey iris", "hi iris", "iris", "hey iris!", "hello iris",
    "hey, iris", "wake up iris", "yo iris",
]


class WakeWordListener:
    """
    Background listener that detects "Hey IRIS" and notifies the main loop.
    Thread-safe. Designed to run alongside the CLI prompt loop.
    """

    def __init__(self):
        self.is_listening    = False
        self._thread         = None
        self._stop_event     = threading.Event()
        self._trigger_event  = threading.Event()
        self._last_command   = ""
        self._microphone_ok  = False
        self._recognizer     = None

    # ── Capability check ──────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        """Returns True if all required libraries and a microphone are present."""
        if not HAS_SR or not HAS_PYAUDIO:
            return False
        try:
            with sr.Microphone() as _:
                return True
        except Exception:
            return False

    # ── Control ───────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Start background wake-word listening thread.
        Returns True if started successfully, False if unavailable.
        """
        if not HAS_SR:
            console.print(
                "[bold yellow][WAKE] SpeechRecognition not installed.[/bold yellow]\n"
                "[dim]  Run:  pip install SpeechRecognition pyaudio[/dim]"
            )
            return False

        if not HAS_PYAUDIO:
            console.print(
                "[bold yellow][WAKE] PyAudio not installed — wake word disabled.[/bold yellow]\n"
                "[dim]  Run:  pip install pyaudio[/dim]"
            )
            return False

        try:
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold     = 300
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold      = 0.8

            # Test microphone access
            with sr.Microphone() as mic:
                self._recognizer.adjust_for_ambient_noise(mic, duration=0.5)
            self._microphone_ok = True

        except Exception as ex:
            console.print(f"[bold yellow][WAKE] No microphone detected — wake word disabled.[/bold yellow]")
            debug_log(f"Microphone init failed: {ex}", category="WAKE")
            return False

        self._stop_event.clear()
        self._trigger_event.clear()
        self.is_listening = True

        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="IrisWakeWordListener"
        )
        self._thread.start()

        console.print("[bold bright_cyan][WAKE] Wake word listener started — say 'Hey IRIS' to activate.[/bold bright_cyan]")
        debug_log("Wake word listener started", category="WAKE")
        return True

    def stop(self):
        """Stop the wake-word listener thread."""
        self.is_listening = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        debug_log("Wake word listener stopped", category="WAKE")

    # ── Background listen loop ─────────────────────────────────────

    def _listen_loop(self):
        """Continuously listen for wake word in background thread."""
        while not self._stop_event.is_set():
            try:
                with sr.Microphone() as mic:
                    # Capture short audio chunk with timeout to remain responsive
                    audio = self._recognizer.listen(mic, timeout=3, phrase_time_limit=4)

                # Transcribe locally with Google (free, online) or sphinx (offline)
                try:
                    text = self._recognizer.recognize_google(audio).lower().strip()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    # Network unavailable — try offline sphinx if installed
                    try:
                        text = self._recognizer.recognize_sphinx(audio).lower().strip()
                    except Exception:
                        time.sleep(0.5)
                        continue

                debug_log(f"Heard: '{text}'", category="WAKE")

                # Check for wake phrase
                if any(wake in text for wake in WAKE_PHRASES):
                    debug_log("Wake word detected!", category="WAKE")
                    self._trigger_event.set()

                    # Now listen for the follow-up command
                    time.sleep(0.3)
                    try:
                        with sr.Microphone() as mic:
                            self._recognizer.adjust_for_ambient_noise(mic, duration=0.2)
                            cmd_audio = self._recognizer.listen(mic, timeout=5, phrase_time_limit=10)
                        cmd_text = self._recognizer.recognize_google(cmd_audio).strip()
                        self._last_command = cmd_text
                        debug_log(f"Command captured: '{cmd_text}'", category="WAKE")
                    except Exception:
                        self._last_command = ""

            except sr.WaitTimeoutError:
                continue  # No speech — keep looping
            except Exception as ex:
                log_exception(ex, context="WAKE_LOOP")
                time.sleep(1)

    # ── Trigger interface ──────────────────────────────────────────

    def wait_for_trigger(self, timeout: float = 0.1) -> tuple[bool, str]:
        """
        Non-blocking poll for wake word trigger.
        Returns (triggered, command_text).
        Call this from the main loop on each iteration.
        """
        fired = self._trigger_event.wait(timeout=timeout)
        if fired:
            self._trigger_event.clear()
            cmd = self._last_command
            self._last_command = ""
            return True, cmd
        return False, ""

    def capture_one_command(self) -> str:
        """
        Blocking: listen for exactly one spoken command and return the text.
        Used after manual '/listen' activation.
        """
        if not HAS_SR or not HAS_PYAUDIO or not self._recognizer:
            return ""
        try:
            console.print("[bold bright_cyan]  [MIC] Listening...[/bold bright_cyan]")
            with sr.Microphone() as mic:
                self._recognizer.adjust_for_ambient_noise(mic, duration=0.3)
                audio = self._recognizer.listen(mic, timeout=8, phrase_time_limit=12)
            text = self._recognizer.recognize_google(audio).strip()
            console.print(f"[dim cyan]  [MIC] Heard: {text}[/dim cyan]")
            return text
        except sr.WaitTimeoutError:
            console.print("[dim yellow]  [MIC] No speech detected.[/dim yellow]")
            return ""
        except Exception as ex:
            console.print(f"[bold red][MIC] Recognition error: {ex}[/bold red]")
            return ""


# ── Global Singleton ──────────────────────────────────────────────
wake_word_listener = WakeWordListener()
