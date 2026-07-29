"""
IRIS AI - Gemini Coding Engine
Provides streaming AI responses from Google Gemini for Coding Mode only.
Uses google-generativeai SDK. Activated via /code command or coding intent detection.
"""

import os
import traceback
from rich.console import Console
from debug_logger import debug_log, log_exception

console = Console()


class GeminiCodingEngine:
    """Gemini-powered Coding Mode engine for IRIS AI."""

    MODEL_PRIMARY  = "gemini-1.5-flash"
    MODEL_FALLBACK = "gemini-1.5-pro"

    CODING_SYSTEM_PROMPT = (
        "You are IRIS AI in Coding Mode — a world-class software engineer and AI pair programmer.\n"
        "You are powered by Gemini and specialize in:\n"
        "  - Writing clean, production-ready code in any language\n"
        "  - Debugging and fixing bugs with clear explanations\n"
        "  - Refactoring and improving existing code\n"
        "  - Explaining code line by line when asked\n"
        "  - Multi-file project modifications\n"
        "  - Architecture and design pattern advice\n\n"
        "RULES:\n"
        "  - Always show complete, working code — never truncate or use '...' placeholders\n"
        "  - Use proper code blocks with language tags (```python, ```javascript, etc.)\n"
        "  - Explain your reasoning briefly before and after code\n"
        "  - If a bug fix is needed, explain what was wrong AND why your fix works\n"
        "  - Keep non-code explanations concise — the user is a developer\n"
        "  - Address the user as 'Boss' naturally\n"
    )

    def __init__(self):
        self.api_key = None
        self.model   = None
        self.chat    = None
        self._initialized = False

    # ── Initialization ────────────────────────────────────────────

    def initialize(self) -> bool:
        """
        Lazy-initialize Gemini client using key from key_manager.
        Returns True if ready, False if key is missing or library not installed.
        """
        from key_manager import get_gemini_api_key
        key = get_gemini_api_key()
        if not key:
            return False

        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel(
                self.MODEL_PRIMARY,
                system_instruction=self.CODING_SYSTEM_PROMPT,
            )
            self.chat  = self.model.start_chat(history=[])
            self.api_key = key
            self._initialized = True
            debug_log("Gemini Coding Engine initialized", category="GEMINI")
            return True
        except ImportError:
            console.print(
                "[bold red][GEMINI] google-generativeai is not installed.[/bold red]\n"
                "[dim]Run:  pip install google-generativeai[/dim]"
            )
            return False
        except Exception as ex:
            console.print(f"[bold red][GEMINI] Initialization failed:[/bold red] {ex}")
            log_exception(ex, context="GEMINI_INIT")
            return False

    def is_ready(self) -> bool:
        """Return True if engine is initialized and Gemini key is present."""
        if self._initialized:
            return True
        return self.initialize()

    def reset_chat(self):
        """Start a fresh Gemini chat session (clears Coding Mode history)."""
        if self.model:
            self.chat = self.model.start_chat(history=[])

    # ── Streaming Query ───────────────────────────────────────────

    def stream_code_query(self, prompt: str, file_context: str = "") -> "Generator[str, None, None]":
        """
        Stream a coding response from Gemini.
        Yields text chunks in real-time for UI rendering.

        Args:
            prompt: The user's coding question or request.
            file_context: Optional raw source code to include as context.
        """
        if not self.is_ready():
            yield (
                "\n[GEMINI] Coding Mode is not available.\n"
                "Run  update gemini api  to add your Gemini API key.\n"
                "Get a free key at: https://aistudio.google.com/app/apikey\n"
            )
            return

        full_prompt = prompt
        if file_context.strip():
            full_prompt = (
                f"Here is the code/context I'm working with:\n\n"
                f"```\n{file_context.strip()}\n```\n\n"
                f"{prompt}"
            )

        try:
            import google.generativeai as genai
            response = self.chat.send_message(full_prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            debug_log(f"Gemini stream complete for prompt: {prompt[:60]}", category="GEMINI")

        except Exception as ex:
            ex_str = str(ex).lower()

            # Key expired or revoked mid-session — re-prompt
            if "api key" in ex_str or "401" in ex_str or "403" in ex_str:
                self._initialized = False
                yield (
                    "\n[GEMINI] API key rejected. Your Gemini key may have expired.\n"
                    "Run  update gemini api  to enter a new key.\n"
                )
                return

            # Model overloaded → try fallback model
            if "503" in ex_str or "overload" in ex_str or "unavailable" in ex_str:
                try:
                    import google.generativeai as genai
                    fallback = genai.GenerativeModel(
                        self.MODEL_FALLBACK,
                        system_instruction=self.CODING_SYSTEM_PROMPT,
                    )
                    fb_chat = fallback.start_chat(history=[])
                    response = fb_chat.send_message(full_prompt, stream=True)
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text
                    return
                except Exception:
                    pass

            console.print(f"[bold red][GEMINI] Error:[/bold red] {ex}")
            log_exception(ex, context="GEMINI_STREAM")
            yield f"\n[Gemini Error: {ex}]\n"


# ── Global Singleton ──────────────────────────────────────────────
gemini_engine = GeminiCodingEngine()


# ── Coding Intent Detector ────────────────────────────────────────

CODING_KEYWORDS = [
    "write a function", "write a script", "write code", "write me code",
    "create a function", "create a class", "generate code", "code for",
    "fix this", "fix the bug", "debug this", "debug my", "fix my code",
    "refactor", "improve this code", "optimize this", "clean up this code",
    "explain this code", "explain the code", "what does this code do",
    "how does this function", "what is this function",
    "add a feature", "add feature", "implement", "build a",
    "python script", "javascript", "html code", "css for",
    "sql query", "regex for", "write regex",
    "unit test", "write tests", "test this function",
    "make it faster", "make it more efficient",
    "convert this to", "translate this code",
    "what's wrong with", "why is this not working", "why doesn't this work",
    "how do i", "how to implement", "how to write",
    "/code", "coding mode",
]

def detect_coding_intent(user_input: str) -> bool:
    """
    Returns True if the user's message looks like a coding request.
    Used to auto-route to Gemini without requiring '/code' prefix.
    """
    text = user_input.lower().strip()
    return any(kw in text for kw in CODING_KEYWORDS)
