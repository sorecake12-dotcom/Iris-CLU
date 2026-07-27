"""
IRIS AI - Hidden Background Debug Logger
Logs internal processing steps, raw JSON payloads, stack traces, and automation details
silently to 'iris_debug.log' without cluttering the user-facing CLI interface.
"""

import os
import sys
import logging
from datetime import datetime

LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "iris_debug.log"))

# Configure file logging
logger = logging.getLogger("IRIS_DEBUG")
logger.setLevel(logging.DEBUG)

# Create file handler if not already present
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def debug_log(message: str, category: str = "DEBUG"):
    """Write internal debug log message silently to iris_debug.log."""
    try:
        logger.debug(f"[{category}] {message}")
    except Exception:
        pass


def log_json_payload(payload: dict, label: str = "ACTION_PAYLOAD"):
    """Log raw JSON payload to iris_debug.log silently."""
    try:
        import json
        dump_str = json.dumps(payload, indent=2)
        logger.debug(f"[{label}]\n{dump_str}")
    except Exception:
        pass


def log_exception(e: Exception, context: str = "EXCEPTION"):
    """Log full exception stack trace to iris_debug.log silently."""
    try:
        import traceback
        tb_str = traceback.format_exc()
        logger.error(f"[{context}] {type(e).__name__}: {e}\n{tb_str}")
    except Exception:
        pass
