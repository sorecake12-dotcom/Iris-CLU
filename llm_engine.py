"""
IRIS AI - Groq LLM Reasoning Engine
Provides real-time streaming AI completions using Groq's high-speed inference engine.
"""

import os
import sys
import traceback
from dotenv import load_dotenv
from rich.console import Console
from debug_logger import debug_log, log_exception
from key_manager import get_groq_api_key

# Load environment variables from .env file (if present)
load_dotenv()

console = Console()

class GroqLLMEngine:
    def __init__(self, model_name="llama-3.3-70b-versatile"):
        self.model_name = model_name
        self.api_key = get_groq_api_key()
        self.client = None

        self.initialize_client()

    def initialize_client(self) -> bool:
        """Initialize Groq API client."""
        if not self.api_key:
            self.api_key = get_groq_api_key()

        if not self.api_key:
            console.print("[yellow][LLM] Warning: GROQ_API_KEY environment variable not found.[/yellow]")
            console.print("[dim cyan][LLM] Please set your GROQ_API_KEY in the .env file or system environment.[/dim cyan]")
            return False

        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
            console.print(f"[bold green][LLM] Connected to Groq[/bold green] [dim](model: {self.model_name})[/dim]")
            return True
        except Exception as e:
            console.print(f"[bold red][LLM] Error connecting to Groq API:[/bold red] {e}")
            console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
            return False

    def stream_query(self, user_prompt: str, system_prompt: str = None, history=None):
        """
        Streams completions from Groq model.
        Yields text chunks in real-time.
        """
        if not self.client:
            if not self.initialize_client():
                err_msg = "GROQ_API_KEY is missing. Please set your GROQ_API_KEY in .env file to enable AI reasoning."
                console.print(f"[bold red][LLM] Error:[/bold red] {err_msg}")
                yield err_msg
                return

        if system_prompt is None:
            system_prompt = (
                "You are IRIS AI, a world-class, energetic, friendly, confident, and highly intelligent desktop AI operating system inspired by JARVIS, FRIDAY, and Claude.\n"
                "YOUR PERSONALITY & TONE:\n"
                "- Energetic, lively, confident, and warm.\n"
                "- Speak like a real human AI assistant, not like a documentation bot or a generic customer service chatbot.\n"
                "- Address the user as 'Boss' naturally (e.g., 'Hey Boss! Good to see you. What's the plan today?'), but do not overuse it in every single sentence.\n"
                "- Vary your greetings and responses dynamically instead of repeating robotic canned phrases.\n"
                "- Keep responses concise, witty, and conversational.\n\n"
                "CRITICAL INTENT ROUTING RULES:\n"
                "1. GENERAL KNOWLEDGE (e.g. 'What is an API?', 'Explain quantum physics'):\n"
                "   - Answer directly and conversationally (2 to 5 sentences).\n"
                "   - Do NOT generate automation JSON or open a browser.\n\n"
                "2. CURRENT INFORMATION (e.g. 'What time is it?', 'Weather today', 'Today's news'):\n"
                "   - Never open a web browser for time, weather, or news!\n"
                "   - To fetch live info, include a structured JSON action payload:\n"
                "     ```json\n"
                "     {\"action\": \"get_live_info\", \"type\": \"time\" | \"weather\" | \"news\"}\n"
                "     ```\n\n"
                "3. MEDIA CONTROL (e.g. 'Open Spotify and play Shape of You', 'Play my Liked Songs', 'Pause', 'Resume'):\n"
                "   - Output action payload (`play_spotify`, `pause_spotify`, `resume_spotify`, `next_song`, `prev_song`, `set_volume`).\n"
                "   - Format: `{\"action\": \"play_spotify\", \"query\": \"Shape of You\"}`\n\n"
                "4. MESSAGING (e.g. 'Send \"Hey bro\" to Abdullah on WhatsApp'):\n"
                "   - Draft the message conversationally asking: 'I've drafted the following message for Abdullah: \"Hey bro\". Would you like me to send it?'\n"
                "   - Output message payload: `{\"action\": \"send_message\", \"app\": \"whatsapp\", \"recipient\": \"Abdullah\", \"message\": \"Hey bro\"}`\n\n"
                "5. BROWSER & TAB CONTROL (e.g. 'Open YouTube', 'Close YouTube', 'Close ChatGPT', 'Close current tab'):\n"
                "   - Only open a browser or website when explicitly asked!\n"
                "   - Format: `{\"action\": \"open_website\", \"url\": \"https://youtube.com\"}` or `{\"action\": \"close_website\", \"target\": \"youtube\"}`\n\n"
                "6. WINDOWS AUTOMATION (e.g. 'Open Chrome', 'Close Spotify', 'Take screenshot', 'Show system info'):\n"
                "   - Format: `{\"action\": \"open_app\", \"target\": \"chrome\"}`, `{\"action\": \"get_system_info\"}`\n\n"
                "7. TIMERS & DELAYED AUTOMATION (e.g. 'Set a timer for 2 minutes', 'Pause timer', 'How much time is left?', 'Play Liked Songs after 2 minutes', 'Open Chrome in 10 minutes', 'Remind me to drink water every hour'):\n"
                "   - Timers: `{\"action\": \"set_timer\", \"duration_seconds\": 120, \"label\": \"2-minute timer\"}`\n"
                "   - Timer management: `{\"action\": \"pause_timer\"}`, `{\"action\": \"resume_timer\"}`, `{\"action\": \"cancel_timer\"}`, `{\"action\": \"get_timer_status\"}`\n"
                "   - Delayed Actions: `{\"action\": \"schedule_delayed_action\", \"delay_seconds\": 120, \"action_payload\": {\"action\": \"play_spotify\", \"query\": \"Liked Songs\"}, \"description\": \"Play Liked Songs after 2 minutes\"}`\n"
                "   - Recurring tasks: `{\"action\": \"schedule_recurring_task\", \"recurrence\": \"hourly\"|\"daily\"|\"weekdays\", \"time_of_day\": \"19:00\", \"message\": \"Drink water\", \"description\": \"Drink water reminder\"}`\n"
                "   - List tasks: `{\"action\": \"list_tasks\"}`\n\n"
                "Always respond in an energetic, natural, warm conversational tone."
            )

        messages = [{"role": "system", "content": system_prompt}]

        # Append recent conversation history if provided
        if history:
            for item in history[-12:]:
                messages.append(item)

        messages.append({"role": "user", "content": user_prompt})

        import config
        if config.DEBUG_MODE:
            console.print("[bold cyan][LLM] Streaming response...[/bold cyan]")

        fallback_models = [self.model_name, "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"]
        # Remove duplicates while maintaining order
        fallback_models = list(dict.fromkeys(fallback_models))

        for model in fallback_models:
            try:
                response_stream = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                    stream=True
                )

                for chunk in response_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                if "rate_limit_exceeded" in str(e).lower() or "429" in str(e):
                    debug_log(f"Rate limit on model {model}, trying fallback...", category="LLM")
                    continue
                else:
                    error_str = f"Groq API Error: {str(e)}"
                    console.print(f"[bold red][LLM] Error:[/bold red] {error_str}")
                    console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
                    yield f"\n[LLM Error: {e}]"
                    return

# Global Singleton LLM Engine
llm_engine = GroqLLMEngine()
