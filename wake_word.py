"""
IRIS AI - Real-Time Voice Mode Engine
Continuous background listener with wake-word detection ("Hey IRIS"),
push-to-talk hotkey (Ctrl + Space), acoustic feedback prevention, microphone status telemetry,
automatic speech recording with VAD silence detection, and voice control commands.
"""

import os
import sys
import re
import time
import ctypes
import threading
from rich.console import Console

import config
from voice_engine import voice_engine
from debug_logger import debug_log, log_exception

console = Console()

# ── Optional Dependencies ─────────────────────────────────────────
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
    "hey, iris", "wake up iris", "yo iris", "ok iris", "okay iris"
]


def play_chime_sound():
    """Play futuristic activation chime when wake word or push-to-talk is triggered."""
    try:
        from ui import play_audio_beep
        play_audio_beep(frequency=1600, duration_ms=80)
    except Exception:
        pass


class WakeWordListener:
    """
    Real-Time Hands-Free Voice Engine for IRIS AI:
    - Background listening thread (works globally anywhere in Windows).
    - Status telemetry: 🎤 Idle | 🎤 Listening | 🎤 Processing | 🎤 Speaking.
    - Push-to-Talk hotkey: Ctrl + Space.
    - Acoustic feedback prevention (pauses mic while IRIS is speaking).
    - Natural voice commands: "Stop listening", "Start listening", "Sleep", "Wake up".
    """

    def __init__(self):
        self.is_listening = False
        self.mic_enabled = True
        self.is_sleeping = False
        self.current_status = "idle"  # "idle" | "listening" | "processing" | "speaking"

        self._thread = None
        self._stop_event = threading.Event()
        self._trigger_event = threading.Event()
        self._last_command = ""
        self._microphone_ok = False
        self._recognizer = None

    @staticmethod
    def is_available() -> bool:
        """Returns True if SpeechRecognition, PyAudio, and a microphone are present."""
        if not HAS_SR or not HAS_PYAUDIO:
            return False
        try:
            with sr.Microphone() as _:
                return True
        except Exception:
            return False

    def get_status_badge(self) -> str:
        """Returns current microphone status badge for UI display."""
        if not self.mic_enabled:
            return "[bold red]🎤 Mic Disabled[/bold red]"
        if self.is_sleeping:
            return "[bold yellow]🎤 Sleeping[/bold yellow]"
        if getattr(voice_engine, "is_playing", False):
            return "[bold cyan]🎤 Speaking[/bold cyan]"

        status_map = {
            "idle": "[dim green]🎤 Idle[/dim green]",
            "listening": "[bold bright_cyan]🎤 Listening...[/bold bright_cyan]",
            "processing": "[bold bright_yellow]🎤 Processing...[/bold bright_yellow]",
            "speaking": "[bold cyan]🎤 Speaking[/bold cyan]",
        }
        return status_map.get(self.current_status, "[dim green]🎤 Idle[/dim green]")

    def start(self) -> bool:
        """Start background wake-word listening thread."""
        if not HAS_SR or not HAS_PYAUDIO:
            console.print("[bold yellow][WAKE] Microphone dependencies missing (SpeechRecognition / PyAudio).[/bold yellow]")
            return False

        try:
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold = 0.8  # Silence detection threshold

            with sr.Microphone() as mic:
                self._recognizer.adjust_for_ambient_noise(mic, duration=0.4)
            self._microphone_ok = True

        except Exception as ex:
            console.print("[bold yellow][WAKE] No microphone detected — voice mode disabled.[/bold yellow]")
            debug_log(f"Microphone init failed: {ex}", category="WAKE")
            return False

        self._stop_event.clear()
        self._trigger_event.clear()
        self.is_listening = True
        self.mic_enabled = True
        self.is_sleeping = False
        self.current_status = "idle"

        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="IrisRealTimeVoiceMode"
        )
        self._thread.start()

        console.print("[bold bright_cyan]🎤 Voice Mode Online — Say 'Hey IRIS' or press Ctrl+Space anywhere in Windows.[/bold bright_cyan]")
        debug_log("Real-time Voice Mode started", category="WAKE")
        return True

    def stop(self):
        """Stop background listening thread."""
        self.is_listening = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        debug_log("Voice Mode stopped", category="WAKE")

    def _check_push_to_talk(self) -> bool:
        """Win32 global hotkey check: returns True if Ctrl + Space is pressed anywhere in Windows."""
        if sys.platform != "win32":
            return False
        try:
            user32 = ctypes.windll.user32
            ctrl_down = bool(user32.GetAsyncKeyState(0x11) & 0x8000)   # VK_CONTROL
            space_down = bool(user32.GetAsyncKeyState(0x20) & 0x8000)  # VK_SPACE
            return ctrl_down and space_down
        except Exception:
            return False

    def _listen_loop(self):
        """Continuous background listening thread for wake words, hotkeys, and speech."""
        while not self._stop_event.is_set():
            time.sleep(0.04)

            # 1. Respect Mic Toggle & Sleep State
            if not self.mic_enabled or self.is_sleeping:
                self.current_status = "disabled" if not self.mic_enabled else "sleeping"
                time.sleep(0.2)
                continue

            # 2. Acoustic Feedback Prevention: Pause microphone while IRIS is speaking TTS!
            if getattr(voice_engine, "is_playing", False) or getattr(voice_engine.speech_queue, "qsize", lambda: 0)() > 0:
                self.current_status = "speaking"
                time.sleep(0.15)
                continue

            self.current_status = "idle"

            # 3. Check Global Push-To-Talk Hotkey (Ctrl + Space)
            if self._check_push_to_talk():
                debug_log("Push-To-Talk hotkey (Ctrl+Space) triggered!", category="WAKE")
                play_chime_sound()
                self._capture_speech_and_trigger(is_ptt=True)
                continue

            # 4. Background Wake Word Detection
            try:
                with sr.Microphone() as mic:
                    # Short ambient chunk to detect wake word
                    audio = self._recognizer.listen(mic, timeout=1.5, phrase_time_limit=3.5)

                try:
                    text = self._recognizer.recognize_google(audio).lower().strip()
                except (sr.UnknownValueError, sr.RequestError):
                    continue

                if not text:
                    continue

                # Instant STOP interrupt check
                if any(w in text for w in ["stop", "pause", "shut up", "quiet", "halt"]):
                    voice_engine.stop_speech()
                    continue

                # Check wake phrase match
                if any(wake in text for wake in WAKE_PHRASES):
                    debug_log(f"Wake word detected in: '{text}'", category="WAKE")
                    play_chime_sound()

                    # Print status and speak natural confirmation
                    console.print("\n[bold bright_cyan]🎤 Listening...[/bold bright_cyan] [dim](Say your command)[/dim]")
                    voice_engine.speak("Yes Boss?")

                    # Automatically record command speech until silence
                    self._capture_speech_and_trigger(is_ptt=False)

            except sr.WaitTimeoutError:
                continue
            except Exception as ex:
                log_exception(ex, context="VOICE_LOOP")
                time.sleep(0.5)

    def _capture_speech_and_trigger(self, is_ptt: bool = False):
        """Record command speech automatically until silence is detected, transcribe, and route."""
        self.current_status = "listening"
        try:
            with sr.Microphone() as mic:
                self._recognizer.adjust_for_ambient_noise(mic, duration=0.2)
                cmd_audio = self._recognizer.listen(mic, timeout=6.0, phrase_time_limit=12.0)

            self.current_status = "processing"
            cmd_text = self._recognizer.recognize_google(cmd_audio).strip()

            if cmd_text:
                debug_log(f"Voice Command Captured: '{cmd_text}'", category="WAKE")
                cmd_lower = cmd_text.lower()

                # Handle Voice Control Commands locally
                if cmd_lower in ["stop listening", "disable mic", "turn off mic", "disable microphone"]:
                    self.mic_enabled = False
                    console.print("\n[bold yellow]🎤 Microphone Disabled.[/bold yellow]\n")
                    voice_engine.speak("Microphone disabled.")
                    return

                elif cmd_lower in ["start listening", "enable mic", "turn on mic", "enable microphone"]:
                    self.mic_enabled = True
                    console.print("\n[bold green]🎤 Microphone Enabled.[/bold green]\n")
                    voice_engine.speak("Microphone enabled.")
                    return

                elif cmd_lower in ["sleep", "go to sleep", "night night"]:
                    self.is_sleeping = True
                    console.print("\n[bold yellow]🎤 IRIS is sleeping. Say 'Wake up' or press Ctrl+Space.[/bold yellow]\n")
                    voice_engine.speak("Sleeping.")
                    return

                elif cmd_lower in ["wake up", "wake up iris"]:
                    self.is_sleeping = False
                    console.print("\n[bold green]🎤 IRIS is awake and listening.[/bold green]\n")
                    voice_engine.speak("I'm awake Boss.")
                    return

                # Route recognized command to main loop / CommandProcessor
                self._last_command = cmd_text
                self._trigger_event.set()

        except sr.WaitTimeoutError:
            console.print("[dim yellow]🎤 No speech detected.[/dim yellow]")
        except sr.UnknownValueError:
            console.print("[dim yellow]🎤 Could not understand audio.[/dim yellow]")
        except Exception as ex:
            log_exception(ex, context="VOICE_CAPTURE_FAILED")
        finally:
            self.current_status = "idle"

    def wait_for_trigger(self, timeout: float = 0.05) -> tuple[bool, str]:
        """Poll for recognized spoken command trigger."""
        fired = self._trigger_event.wait(timeout=timeout)
        if fired:
            self._trigger_event.clear()
            cmd = self._last_command
            self._last_command = ""
            return True, cmd
        return False, ""

    def capture_one_command(self) -> str:
        """Manual one-shot command capture for /listen command."""
        if not HAS_SR or not HAS_PYAUDIO or not self._recognizer:
            return ""
        try:
            play_chime_sound()
            console.print("[bold bright_cyan]🎤 Listening... Speak now.[/bold bright_cyan]")
            self.current_status = "listening"
            with sr.Microphone() as mic:
                self._recognizer.adjust_for_ambient_noise(mic, duration=0.3)
                audio = self._recognizer.listen(mic, timeout=7.0, phrase_time_limit=12.0)
            self.current_status = "processing"
            text = self._recognizer.recognize_google(audio).strip()
            console.print(f"[dim cyan]🎤 Recognized: '{text}'[/dim cyan]")
            return text
        except Exception as ex:
            console.print(f"[dim yellow]🎤 Speech capture error: {ex}[/dim yellow]")
            return ""
        finally:
            self.current_status = "idle"


# Global Singleton Voice Listener Engine
wake_word_listener = WakeWordListener()
