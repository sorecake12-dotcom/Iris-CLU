"""
IRIS AI - Production-Ready Local Voice Cloning & Speech Engine
Scans reference voices from SOURCE_VOICE_PATH to PROJECT_VOICE_PATH,
caches cloned voice reference, and handles low-latency audio synthesis and playback.
"""

import os
import sys
import re
import time
import queue
import shutil
import threading
import glob
import traceback
from rich.console import Console

import config
from debug_logger import debug_log, log_exception

console = Console()

SOURCE_VOICE_PATH = r"C:\Users\ACER\OneDrive\Desktop\IRIS CLU\voice\tts-audio.wav"
PROJECT_VOICE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "voice"))
VALID_EXTENSIONS = (".wav", ".mp3", ".flac")

# Optional pythoncom for Windows COM initialization in worker thread
try:
    import pythoncom
    HAS_PYTHONCOM = True
except ImportError:
    HAS_PYTHONCOM = False


class VoiceEngine:
    def __init__(self, voice_dir=PROJECT_VOICE_PATH, source_path=SOURCE_VOICE_PATH):
        self.voice_dir = os.path.abspath(voice_dir)

        if os.path.exists(source_path):
            self.source_path = os.path.abspath(source_path)
        else:
            alt_source = r"C:\Users\ACER\Music\tts-audio.wav"
            if os.path.exists(alt_source):
                self.source_path = os.path.abspath(alt_source)
            else:
                self.source_path = os.path.abspath(source_path)

        os.makedirs(self.voice_dir, exist_ok=True)

        self.current_voice_file = None
        self.cached_mtime = 0
        self.cloning_active = False
        self.cloned_speaker_ref = None

        self.speech_queue = queue.Queue()
        self.interrupt_event = threading.Event()
        self.is_playing = False
        self.engine_lock = threading.Lock()

        self.xtts_model = None
        self.load_error_details = None

        # 1. Verify & Copy Source Voice if needed
        self.ensure_source_voice_copied()

        # 2. Initialize cloning backend model
        self._init_cloning_backend()

        # 3. Scan & load custom reference voice with detailed startup logs
        self.scan_and_load_voice(verbose=True)

        # 4. Start asynchronous speech queue worker
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _init_cloning_backend(self):
        """Initialize XTTS v2 or local voice-cloning model if available."""
        try:
            from TTS.api import TTS
            self.xtts_model = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
            self.load_error_details = None
            debug_log("XTTS v2 voice cloning backend initialized successfully.", category="VOICE")
        except Exception as ex:
            self.xtts_model = None
            self.load_error_details = {
                "exception": type(ex).__name__,
                "reason": str(ex),
                "file": __file__,
                "traceback": traceback.format_exc()
            }
            log_exception(ex, context="VOICE_BACKEND_INIT")

    def ensure_source_voice_copied(self):
        """Automatically copy reference voice from SOURCE_VOICE_PATH to PROJECT_VOICE_PATH if needed."""
        try:
            if os.path.exists(self.source_path) and os.path.isfile(self.source_path):
                dest_file = os.path.join(self.voice_dir, os.path.basename(self.source_path))
                if not os.path.exists(dest_file):
                    shutil.copy2(self.source_path, dest_file)
            else:
                existing_files = []
                for ext in VALID_EXTENSIONS:
                    existing_files.extend(glob.glob(os.path.join(self.voice_dir, f"*{ext}")))
                if existing_files:
                    self.source_path = os.path.abspath(existing_files[0])
        except Exception as e:
            console.print(f"[bold red][VOICE ERROR] Error copying reference voice: {e}[/bold red]")
            log_exception(e, context="VOICE_COPY")

    def scan_and_load_voice(self, verbose=False) -> bool:
        """
        Scans PROJECT_VOICE_PATH for valid audio files (.wav, .mp3, .flac).
        Loads the first valid reference voice and caches it in memory.
        """
        with self.engine_lock:
            self.ensure_source_voice_copied()

            audio_files = []
            for ext in VALID_EXTENSIONS:
                audio_files.extend(glob.glob(os.path.join(self.voice_dir, f"*{ext}")))
                audio_files.extend(glob.glob(os.path.join(self.voice_dir, f"*{ext.upper()}")))

            audio_files = sorted(list(set(audio_files)))

            if not audio_files:
                if verbose:
                    console.print(f"[bold yellow][VOICE] Warning: No reference voice (.wav, .mp3, .flac) found in {self.voice_dir}[/bold yellow]")
                    if self.load_error_details:
                        debug_log(f"Voice load notice: {self.load_error_details['reason']}", category="VOICE")
                    console.print("[dim cyan][TTS] High-Definition Neural Voice Active (Edge TTS)[/dim cyan]")
                self.current_voice_file = None
                self.cloning_active = False
                return False

            selected_file = os.path.abspath(audio_files[0])
            current_mtime = os.path.getmtime(selected_file)

            if selected_file != self.current_voice_file or current_mtime != self.cached_mtime:
                self.current_voice_file = selected_file
                self.cached_mtime = current_mtime
                self.cloned_speaker_ref = selected_file

            fn = os.path.basename(self.current_voice_file)

            if verbose or config.DEBUG_MODE:
                console.print(f"[dim green][VOICE] Found reference voice: {fn}[/dim green]")
                console.print(f"[dim green][VOICE] Loaded: {fn}[/dim green]")
                debug_log(f"Loaded reference voice file: {self.current_voice_file}", category="VOICE")

            if self.xtts_model is not None:
                self.cloning_active = True
                if verbose or config.DEBUG_MODE:
                    console.print("[dim green][VOICE] Voice cloning initialized[/dim green]")
                    console.print("[dim green][VOICE] Custom voice active[/dim green]")
                    console.print("[dim green][TTS] Ready[/dim green]")
                return True
            else:
                self.cloning_active = False
                if verbose or config.DEBUG_MODE:
                    console.print(f"[bold red][VOICE ERROR] Voice cloning backend model failed to load.[/bold red]")
                    if self.load_error_details:
                        console.print(f"[bold red][VOICE ERROR] Exception:[/bold red] {self.load_error_details['exception']}")
                        console.print(f"[bold red][VOICE ERROR] Reason:[/bold red] {self.load_error_details['reason']}")
                    console.print("[dim cyan][TTS] High-Definition Neural Voice Active (Edge TTS)[/dim cyan]")
                    console.print("[dim green][TTS] Ready[/dim green]")
                return False

    def prepare_speech_text(self, text: str) -> str:
        """
        Sanitizes and extracts a short, natural speech version for TTS:
        - Removes code blocks, URLs, markdown symbols, and headings.
        - Keeps up to 2-4 key conversational sentences (max ~50 words) for natural speech.
        """
        if not text:
            return ""

        text = re.sub(r"```[\s\S]*?```", " Code block provided on screen. ", text)
        text = re.sub(r"`[^`]*`", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"^[#\-\*\+]+\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"[#*_\-+=~|\\\[\]]", " ", text)
        text = re.sub(r"\[::\]|\[\+\]|\[VOICE\]|\[LLM\]|\[TTS\]|\[AUDIO\]|❖", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return ""

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        selected_sentences = sentences[:3]
        spoken_text = " ".join(selected_sentences)

        words = spoken_text.split()
        if len(words) > 55:
            spoken_text = " ".join(words[:55]) + "."

        return spoken_text

    def speak(self, text: str):
        """Enqueue prepared assistant response for speech synthesis."""
        cleaned_speech = self.prepare_speech_text(text)
        if not cleaned_speech:
            return

        self.interrupt_event.clear()

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned_speech) if s.strip()]
        for sentence in sentences:
            self.speech_queue.put(sentence)

    def stop_speech(self):
        """Interrupt active speech playback immediately and clear queue."""
        self.interrupt_event.set()
        with self.speech_queue.mutex:
            self.speech_queue.queue.clear()

    def _worker_loop(self):
        """Background worker consuming speech queue in a thread-safe COM environment."""
        if HAS_PYTHONCOM and sys.platform == "win32":
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        while True:
            try:
                sentence = self.speech_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            self.interrupt_event.clear()
            self.is_playing = True

            max_retries = 2
            played_successfully = False
            last_error = None

            for attempt in range(1, max_retries + 1):
                if self.interrupt_event.is_set():
                    break
                try:
                    self._synthesize_and_play(sentence)
                    played_successfully = True
                    break
                except Exception as e:
                    last_error = e
                    log_exception(e, context=f"SPEECH_PLAYBACK_ATTEMPT_{attempt}")
                    if attempt < max_retries:
                        time.sleep(0.1)

            if not played_successfully and not self.interrupt_event.is_set() and last_error:
                console.print(f"[bold red][AUDIO ERROR] Speech playback failed: {last_error}[/bold red]")

            self.is_playing = False
            self.speech_queue.task_done()

    def _create_thread_pyttsx3_engine(self):
        """Create a fresh pyttsx3 engine instance bound to the current worker thread."""
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)
        try:
            voices = engine.getProperty("voices")
            for voice in voices:
                if any(w in voice.name.lower() for w in ["david", "zira", "english", "hazel"]):
                    engine.setProperty("voice", voice.id)
                    break
        except Exception:
            pass
        return engine

    def _synthesize_and_play(self, sentence: str):
        """
        Synthesize audio using custom cloned reference voice from PROJECT_VOICE_PATH.
        Guarantees custom reference voice is passed directly to voice-cloning model.
        """
        if self.interrupt_event.is_set() or not sentence.strip():
            return

        self.scan_and_load_voice(verbose=False)

        # 1. Custom Cloned Voice Synthesis (XTTS v2)
        if self.cloning_active and self.current_voice_file and self.xtts_model:
            if config.DEBUG_MODE:
                console.print("[dim cyan][TTS] Using cloned voice[/dim cyan]")
                console.print("[dim green][AUDIO] Playback started[/dim green]")

            import tempfile
            import sounddevice as sd
            import soundfile as sf

            temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_wav.close()

            try:
                self.xtts_model.tts_to_file(
                    text=sentence,
                    speaker_wav=self.current_voice_file,
                    language="en",
                    file_path=temp_wav.name
                )

                data, fs = sf.read(temp_wav.name)
                sd.play(data, fs)

                while sd.get_stream().active:
                    if self.interrupt_event.is_set():
                        sd.stop()
                        break
                    time.sleep(0.04)

                if config.DEBUG_MODE:
                    console.print("[dim green][AUDIO] Playback completed[/dim green]")
                return
            except Exception as ex:
                if config.DEBUG_MODE:
                    console.print(f"[bold red][VOICE ERROR] Synthesis failed with custom voice {self.current_voice_file}: {ex}[/bold red]")
                log_exception(ex, context="CLONED_VOICE_SYNTHESIS")
                raise ex
            finally:
                if os.path.exists(temp_wav.name):
                    try:
                        os.remove(temp_wav.name)
                    except Exception:
                        pass

        # 2. High-Quality Neural Voice Synthesis (Edge TTS)
        if not self.interrupt_event.is_set():
            try:
                import asyncio
                import edge_tts
                import tempfile
                import ctypes

                temp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                temp_mp3.close()

                async def _synth_edge():
                    communicate = edge_tts.Communicate(sentence, "en-US-ChristopherNeural")
                    await communicate.save(temp_mp3.name)

                asyncio.run(_synth_edge())

                if config.DEBUG_MODE:
                    console.print("[dim cyan][TTS] Using Neural Voice (en-US-ChristopherNeural)[/dim cyan]")
                    console.print("[dim green][AUDIO] Playback started[/dim green]")

                mci = ctypes.windll.winmm.mciSendStringW
                alias = f"mp3_{int(time.time()*1000)}"
                mci(f'open "{temp_mp3.name}" type mpegvideo alias {alias}', None, 0, 0)
                mci(f'play {alias}', None, 0, 0)

                buf = ctypes.create_unicode_buffer(128)
                while True:
                    if self.interrupt_event.is_set():
                        mci(f'stop {alias}', None, 0, 0)
                        break
                    mci(f'status {alias} mode', buf, 128, 0)
                    if buf.value != "playing":
                        break
                    time.sleep(0.05)

                mci(f'close {alias}', None, 0, 0)

                if config.DEBUG_MODE:
                    console.print("[dim green][AUDIO] Playback completed[/dim green]")
                if os.path.exists(temp_mp3.name):
                    try:
                        os.remove(temp_mp3.name)
                    except Exception:
                        pass
                return
            except Exception as edge_err:
                log_exception(edge_err, context="EDGE_TTS_SYNTHESIS")

        # 3. System SAPI5 TTS Fallback (pyttsx3)
        if not self.interrupt_event.is_set():
            if config.DEBUG_MODE:
                console.print("[dim yellow][TTS] Standard system TTS fallback active[/dim yellow]")
                console.print("[dim green][AUDIO] Playback started[/dim green]")

            engine = self._create_thread_pyttsx3_engine()
            engine.say(sentence)
            engine.runAndWait()
            engine.stop()

            if config.DEBUG_MODE:
                console.print("[dim green][AUDIO] Playback completed[/dim green]")


# Global Singleton Voice Engine
voice_engine = VoiceEngine()
