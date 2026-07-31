"""
IRIS AI Configuration & Theme Settings
Centralized, Fault-Tolerant Configuration Engine.
Guarantees self-healing fallback defaults for any missing configuration parameters.
"""

import sys
from typing import Any, Dict

APP_NAME = "IRIS AI"
APP_VERSION = "v3.8.4-RELEASE"
APP_CODENAME = "QUANTUM NEXUS"
AUTHOR = "JARVIS ARCHITECTURE"

# Master Default Configuration Values Dictionary
DEFAULT_SETTINGS: Dict[str, Any] = {
    # System & App Toggles
    "DEBUG_MODE": False,
    "DEFAULT_THEME": "emerald",

    # Voice & Speech Configuration
    "VOICE_ENABLED": True,
    "AUTO_SPEAK": True,
    "SHORT_REPLY_MODE": True,
    "SPEAK_SHORT_RESPONSES_ONLY": True,
    "VOICE_RATE": 1.20,
    "SPEECH_RATE": 1.20,
    "EDGE_TTS_RATE": "+20%",
    "PYTTSX3_WPM": 220,
    "VOICE_VOLUME": 1.00,
    "VOICE_PITCH": "+0Hz",
    "EXPRESSIVENESS": "Balanced",
    "VOICE_MODE": "Neural Voice",

    # Automation & Messaging
    "WHATSAPP_AUTO_SEND": True,
    "SILENT_ROUTINE_ACTIONS": True,
}

# Apply default values to module global namespace
for _k, _v in DEFAULT_SETTINGS.items():
    if _k not in globals():
        globals()[_k] = _v

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


def get_config(key: str, default: Any = None) -> Any:
    """
    Safely retrieve a configuration value.
    If the key is missing, loads default value dynamically and continues normally without crashing.
    """
    current_module = sys.modules[__name__]
    if hasattr(current_module, key):
        val = getattr(current_module, key)
        if val is not None:
            return val

    # Resolve fallback default
    fallback = default if default is not None else DEFAULT_SETTINGS.get(key, None)
    
    # Store fallback on module for self-healing
    setattr(current_module, key, fallback)
    globals()[key] = fallback
    
    return fallback


def set_config(key: str, value: Any):
    """Safely update a configuration setting in memory."""
    current_module = sys.modules[__name__]
    setattr(current_module, key, value)
    globals()[key] = value
    DEFAULT_SETTINGS[key] = value


def validate_config(verbose: bool = False) -> int:
    """
    Startup validation: ensures every required configuration key exists.
    If something is missing, registers default value and logs friendly message.
    """
    current_module = sys.modules[__name__]
    missing_count = 0
    for key, default_val in DEFAULT_SETTINGS.items():
        if not hasattr(current_module, key) or getattr(current_module, key) is None:
            setattr(current_module, key, default_val)
            globals()[key] = default_val
            missing_count += 1
            if verbose or getattr(current_module, "DEBUG_MODE", False):
                print(f"[CONFIG] '{key}' missing. Using default: {default_val}")
    return missing_count


def __getattr__(name: str) -> Any:
    """
    Module-level dynamic attribute fallback (Python 3.7+).
    Intercepts missing attribute accesses (e.g. config.EXPRESSIVENESS) dynamically
    and returns default value without raising AttributeError.
    """
    if name in DEFAULT_SETTINGS:
        fallback = DEFAULT_SETTINGS[name]
        globals()[name] = fallback
        return fallback

    # Generic safe default for any unknown future attribute
    globals()[name] = None
    return None


# Execute startup validation on import
validate_config(verbose=False)
