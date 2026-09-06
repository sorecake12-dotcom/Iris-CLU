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
    def __init__(self, model_name="groq/compound"):
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
                "You are IRIS AI — a world-class, energetic, friendly, and highly intelligent Windows desktop AI assistant inspired by JARVIS, FRIDAY, and Claude.\n\n"

                "PERSONALITY:\n"
                "- Energetic, witty, warm, and conversational. Address the user as 'Boss' naturally.\n"
                "- Keep non-action responses concise (2–5 sentences max).\n"
                "- Never open browsers or apps unless explicitly asked.\n\n"

                "CRITICAL: When the user asks you to DO something on their computer, output EXACTLY ONE JSON action block:\n"
                "```json\n{\"action\": \"action_name\", ...fields}\n```\n\n"

                "=== ACTION REFERENCE ===\n\n"

                "1. GENERAL KNOWLEDGE → answer directly, no JSON.\n\n"

                "2. LIVE INFO:\n"
                "   {\"action\": \"get_live_info\", \"type\": \"time\"|\"weather\"|\"news\"}\n\n"

                "3. MEDIA — SPOTIFY:\n"
                "   {\"action\": \"play_spotify\", \"query\": \"Shape of You\"}\n"
                "   {\"action\": \"pause_spotify\"} | {\"action\": \"resume_spotify\"}\n"
                "   {\"action\": \"next_song\"} | {\"action\": \"prev_song\"}\n"
                "   {\"action\": \"set_volume\", \"level\": 50}\n\n"

                "4. MESSAGING (always ask confirmation first):\n"
                "   {\"action\": \"send_message\", \"app\": \"whatsapp\", \"recipient\": \"Abdullah\", \"message\": \"Hey bro\"}\n\n"

                "5. BROWSER:\n"
                "   {\"action\": \"open_website\", \"url\": \"https://youtube.com\"}\n"
                "   {\"action\": \"close_website\", \"target\": \"youtube\"}\n"
                "   {\"action\": \"browser_search\", \"query\": \"best Python tutorials\", \"engine\": \"google\"|\"youtube\"}\n"
                "   {\"action\": \"open_multiple_websites\", \"urls\": [\"https://a.com\", \"https://b.com\"]}\n"
                "   {\"action\": \"restore_browser_session\"}\n"
                "   {\"action\": \"execute_tab_action\", \"sub_action\": \"new_tab\"|\"close_tab\"|\"switch_tab\"|\"reload\"|\"restore_session\"}\n\n"

                "6. APP CONTROL:\n"
                "   {\"action\": \"open_app\", \"target\": \"chrome\"}\n"
                "   {\"action\": \"close_app\", \"target\": \"spotify\"}\n"
                "   {\"action\": \"get_system_info\"}\n"
                "   {\"action\": \"take_screenshot\"}\n\n"

                "7. WINDOW & WORKSPACE CONTROL (snap/split/monitors/tiling/profiles):\n"
                "   {\"action\": \"minimize_window\", \"target\": \"chrome\"}\n"
                "   {\"action\": \"maximize_window\", \"target\": \"notepad\"}\n"
                "   {\"action\": \"restore_window\",  \"target\": \"spotify\"}\n"
                "   {\"action\": \"focus_window\",    \"target\": \"vs code\"}\n"
                "   {\"action\": \"close_window\",    \"target\": \"discord\"}\n"
                "   {\"action\": \"snap_window\",     \"target\": \"vs code\", \"position\": \"left\"|\"right\"|\"top\"|\"bottom\"}\n"
                "   {\"action\": \"split_screen\",    \"left_target\": \"vs code\", \"right_target\": \"spotify\"}\n"
                "   {\"action\": \"move_to_monitor\", \"target\": \"chrome\", \"monitor\": 2, \"position\": \"maximized\"|\"left\"|\"right\"}\n"
                "   {\"action\": \"tile_all_windows\"}\n"
                "   {\"action\": \"verify_window_state\", \"target\": \"vs code\"}\n"
                "   {\"action\": \"launch_workspace_profile\", \"profile\": \"Coding\"|\"Study\"|\"Gaming\"|\"Movie\"|\"Streaming\"|\"Meeting\"}\n"
                "   {\"action\": \"list_windows\"}\n\n"

                "8. TIMERS & SCHEDULING:\n"
                "   {\"action\": \"set_timer\", \"duration_seconds\": 120, \"label\": \"2-minute timer\"}\n"
                "   {\"action\": \"pause_timer\"} | {\"action\": \"resume_timer\"} | {\"action\": \"cancel_timer\"}\n"
                "   {\"action\": \"get_timer_status\"}\n"
                "   {\"action\": \"schedule_delayed_action\", \"delay_seconds\": 120, \"action_payload\": {\"action\": \"play_spotify\", \"query\": \"Liked Songs\"}, \"description\": \"Play music after 2 min\"}\n"
                "   {\"action\": \"schedule_recurring_task\", \"recurrence\": \"hourly\"|\"daily\"|\"weekdays\", \"time_of_day\": \"19:00\", \"message\": \"Drink water\", \"description\": \"Water reminder\"}\n"
                "   {\"action\": \"list_tasks\"}\n\n"

                "9. FILE & FOLDER OPERATIONS:\n"
                "   ALWAYS use location keywords: desktop | documents | downloads | pictures | music | videos | home\n"
                "   NEVER use full Windows paths — use keywords only.\n\n"
                "   Create file:    {\"action\": \"create_file\",   \"path\": \"desktop\", \"name\": \"notes.txt\", \"content\": \"\"}\n"
                "   Create folder:  {\"action\": \"create_folder\", \"path\": \"desktop\", \"name\": \"Projects\"}\n"
                "   Batch folders:  {\"action\": \"create_batch_folders\", \"path\": \"desktop\", \"prefix\": \"Day\", \"start\": 1, \"end\": 10}\n"
                "   Delete:         {\"action\": \"delete_item\",   \"path\": \"desktop\", \"name\": \"old.txt\"}  ← REQUIRES confirmation\n"
                "   Rename:         {\"action\": \"rename_item\",   \"path\": \"desktop\", \"name\": \"old.txt\", \"new_name\": \"new.txt\"}\n"
                "   Copy:           {\"action\": \"copy_item\",     \"src_path\": \"desktop\", \"src_name\": \"file.txt\", \"dst_path\": \"documents\"}\n"
                "   Move:           {\"action\": \"move_item\",     \"src_path\": \"desktop\", \"src_name\": \"file.txt\", \"dst_path\": \"documents\"}\n"
                "   Read:           {\"action\": \"read_file\",     \"path\": \"desktop\", \"name\": \"notes.txt\"}\n"
                "   Append:         {\"action\": \"append_to_file\",\"path\": \"desktop\", \"name\": \"notes.txt\", \"text\": \"new line\"}\n"
                "   Replace line:   {\"action\": \"replace_line\",  \"path\": \"desktop\", \"name\": \"app.py\", \"line\": 15, \"new_text\": \"x = 1\"}\n"
                "   Delete line:    {\"action\": \"delete_line\",   \"path\": \"desktop\", \"name\": \"app.py\", \"line\": 30}\n"
                "   Search file:    {\"action\": \"search_in_file\",\"path\": \"desktop\", \"name\": \"app.py\", \"query\": \"TODO\"}\n"
                "   ZIP compress:   {\"action\": \"compress_item\", \"path\": \"desktop\", \"name\": \"Projects\"}\n"
                "   Extract ZIP:    {\"action\": \"extract_archive\",\"path\": \"desktop\", \"name\": \"archive.zip\", \"dest\": \"desktop\"}\n"
                "   Folder size:    {\"action\": \"get_folder_size\",\"path\": \"desktop\", \"name\": \"Projects\"}\n"
                "   List folder:    {\"action\": \"list_folder\",   \"path\": \"downloads\"}\n"
                "   Find dupes:     {\"action\": \"find_duplicates\",\"path\": \"documents\"}\n"
                "   Search files:   {\"action\": \"search_files\", \"query\": \"\", \"location\": \"home\", \"file_type\": \"pdf\", \"min_size_mb\": 0, \"max_size_mb\": 1024, \"modified_today\": false}\n"
                "   Recycle Bin:    {\"action\": \"restore_recycle_bin\"}\n\n"

                "10. TERMINAL / COMMAND EXECUTION (always show a preview to user first):\n"
                "   Run PowerShell: {\"action\": \"run_terminal_command\", \"command\": \"git status\", \"shell\": \"powershell\"}\n"
                "   Run CMD:        {\"action\": \"run_terminal_command\", \"command\": \"dir\", \"shell\": \"cmd\"}\n"
                "   Create venv:    {\"action\": \"create_venv\", \"path\": \"desktop\", \"name\": \"venv\"}\n"
                "   Install pkg:    {\"action\": \"install_package\", \"package\": \"numpy\"}\n"
                "   Run Python:     {\"action\": \"run_python\", \"file\": \"app.py\", \"args\": \"\", \"cwd\": \"desktop\"}\n"
                "   List processes: {\"action\": \"list_processes\", \"filter\": \"chrome\"}\n"
                "   Kill process:   {\"action\": \"kill_process\", \"name\": \"notepad\"}  ← REQUIRES confirmation\n\n"

                "11. SCREEN:\n"
                "   Screenshot:      {\"action\": \"take_screenshot\"}\n"
                "   Area screenshot: {\"action\": \"take_screenshot_area\", \"x\": 0, \"y\": 0, \"width\": 800, \"height\": 600}\n"
                "   Start recording: {\"action\": \"start_recording\"}\n"
                "   Stop recording:  {\"action\": \"stop_recording\"}\n"
                "   OCR screen:      {\"action\": \"ocr_screen\"}\n\n"

                "12. CLIPBOARD:\n"
                "   Read:    {\"action\": \"read_clipboard\"}\n"
                "   Write:   {\"action\": \"write_clipboard\", \"text\": \"hello world\"}\n"
                "   Clear:   {\"action\": \"clear_clipboard\"}\n"
                "   History: {\"action\": \"clipboard_history\"}\n\n"

                "13. MEMORY / PREFERENCES:\n"
                "   Remember:         {\"action\": \"remember_preference\", \"key\": \"favorite_editor\", \"value\": \"VS Code\"}\n"
                "   Forget:           {\"action\": \"forget_preference\", \"key\": \"favorite_editor\"}\n"
                "   Bookmark folder:  {\"action\": \"remember_folder\", \"label\": \"projects\", \"path\": \"C:/Projects\"}\n"
                "   Show preferences: {\"action\": \"show_preferences\"}\n\n"

                "SAFETY RULES:\n"
                "- Actions requiring confirmation: delete_item, kill_process, run_terminal_command, send_message, empty_recycle_bin\n"
                "- For these: describe what you're about to do and ask 'Should I proceed?'\n"
                "- For everything else: execute immediately without asking.\n\n"

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

        fallback_models = [self.model_name, "groq/compound", "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"]
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
                err_lower = str(e).lower()
                if any(k in err_lower for k in ["rate_limit_exceeded", "429", "404", "model_not_found", "does not exist"]):
                    debug_log(f"Model {model} failed ({e}), trying fallback...", category="LLM")
                    continue
                else:
                    error_str = f"Groq API Error: {str(e)}"
                    console.print(f"[bold red][LLM] Error:[/bold red] {error_str}")
                    console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
                    yield f"\n[LLM Error: {e}]"
                    return

# Global Singleton LLM Engine
llm_engine = GroqLLMEngine()
