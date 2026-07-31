"""
IRIS AI Configuration & Theme Settings
"""

APP_NAME = "IRIS AI"
APP_VERSION = "v3.8.4-RELEASE"
APP_CODENAME = "QUANTUM NEXUS"
AUTHOR = "JARVIS ARCHITECTURE"

# Global Debug Mode Toggle (Enabled via --debug flag or /debug command)
DEBUG_MODE = False

# Theme Palettes (Rich formatting strings & HEX colors)
THEMES = {
    "emerald": {
        "name": "Emerald Neon Green",
        "primary": "bright_green",
        "secondary": "spring_green1",
        "accent": "bold bright_green",
        "highlight": "bright_white",
        "alert": "bright_red",
        "success": "bright_green",
        "dim": "dim green",
        "border": "bright_green",
        "prompt_symbol": "::",
        "badge_bg": "on green",
    },
    "jarvis": {
        "name": "Jarvis Electric Blue",
        "primary": "cyan",
        "secondary": "bright_blue",
        "accent": "bold sky_blue1",
        "highlight": "bright_white",
        "alert": "bright_red",
        "success": "bright_green",
        "dim": "dim cyan",
        "border": "cyan",
        "prompt_symbol": "::",
        "badge_bg": "on blue",
    },
    "cyberpunk": {
        "name": "Neon Cyberpunk",
        "primary": "magenta",
        "secondary": "bright_magenta",
        "accent": "bold yellow",
        "highlight": "bright_white",
        "alert": "bright_red",
        "success": "bright_cyan",
        "dim": "dim magenta",
        "border": "magenta",
        "prompt_symbol": ">>",
        "badge_bg": "on dark_magenta",
    },
    "matrix": {
        "name": "Matrix Code Green",
        "primary": "green",
        "secondary": "bright_green",
        "accent": "bold green_yellow",
        "highlight": "bright_white",
        "alert": "bright_red",
        "success": "spring_green1",
        "dim": "dim green",
        "border": "green",
        "prompt_symbol": ">",
        "badge_bg": "on green",
    },
    "solar": {
        "name": "Solar Flare Amber",
        "primary": "yellow",
        "secondary": "bright_yellow",
        "accent": "bold orange1",
        "highlight": "bright_white",
        "alert": "bright_red",
        "success": "gold1",
        "dim": "dim yellow",
        "border": "yellow",
        "prompt_symbol": "*",
        "badge_bg": "on dark_orange",
    }
}

DEFAULT_THEME = "emerald"

# Futuristic Boot Diagnostic Messages
BOOT_MESSAGES = [
    "Initializing Neural Kernel Engine...",
    "Allocating Quantum Memory Buffers...",
    "Calibrating IRIS Core Heuristics...",
    "Establishing Encrypted Telemetry Link...",
    "Synchronizing Subsystem Matrices...",
    "IRIS AI Neural Network Online."
]

# ── Voice & Speech Engine Settings ──
VOICE_ENABLED = True
SPEAK_SHORT_RESPONSES_ONLY = True   # Spoken replies are ultra-concise (default ON)
SPEECH_RATE = 1.25                  # Speech rate multiplier (1.25x = +25% faster)
EDGE_TTS_RATE = "+25%"              # Edge TTS rate parameter (+25% faster)
PYTTSX3_WPM = 220                   # pyttsx3 fallback WPM (220 WPM)
VOICE_VOLUME = 1.0                  # Volume scale (0.0 - 1.0)
VOICE_PITCH = "+0Hz"                # Pitch adjustment
EXPRESSIVENESS = "natural"           # Natural expressiveness mode
SILENT_ROUTINE_ACTIONS = True       # Skip speech for routine actions (copy, paste, min, max, etc.)

