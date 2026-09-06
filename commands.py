"""
IRIS AI Command Processor & Skill Routing Module
Connects user messages to Groq LLM reasoning engine, Windows Automation Engine, and slash command execution matrix.
"""

import sys
import os
import time
import math
import psutil
import platform
from datetime import datetime
from rich.table import Table
from rich.panel import Panel
from rich.console import Console

import config
import banner
import ui
from llm_engine import llm_engine
from voice_engine import voice_engine
from automation_engine import automation_engine, extract_action_intent
from debug_logger import debug_log, log_exception

console = Console()


class CommandProcessor:
    def __init__(self, cli_app):
        self.cli = cli_app
        self.history = []
        self.chat_history = []
        self.pending_action = None

    def process(self, user_input: str) -> bool:
        """
        Processes command or LLM query.
        Returns False if application should exit, True otherwise.
        """
        user_input = user_input.strip()
        if not user_input:
            return True

        self.history.append(user_input)
        cmd_lower = user_input.lower()

        # Handle pending stateful conversational confirmation
        if self.pending_action:
            action_data = self.pending_action
            if any(w in cmd_lower for w in ["yes", "yep", "yeah", "send it", "send", "do it", "go ahead", "sure", "ok", "okay", "confirm"]) or cmd_lower in ["y", "yes"]:
                self.pending_action = None
                act_name = action_data.get("action", "")
                t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
                accent = t["accent"]

                if act_name == "send_message":
                    recip = action_data.get("recipient") or action_data.get("to") or "contact"
                    console.print(f"[{accent}]Sending to {recip}...[/{accent}]")

                exec_result = automation_engine.execute_action(action_data, confirmed=True)
                
                if act_name == "send_message":
                    reply_msg = "✓ Message sent."
                    voice_msg = "Message sent."
                else:
                    reply_msg = f"Done! {exec_result.get('details', 'Action completed.')}"
                    voice_msg = "Done."

                console.print(f"[{accent}]IRIS AI >[/{accent}] {reply_msg}\n")
                voice_engine.speak(voice_msg)
                return True

            elif any(w in cmd_lower for w in ["no", "nope", "cancel", "don't send", "dont send", "stop", "abort"]) or cmd_lower in ["n", "no"]:
                self.pending_action = None
                t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
                accent = t["accent"]
                
                act_name = action_data.get("action", "")
                cancel_msg = "Message cancelled." if act_name == "send_message" else "Action cancelled."
                
                console.print(f"[{accent}]IRIS AI >[/{accent}] {cancel_msg}\n")
                voice_engine.speak(cancel_msg)
                return True

            else:
                self.pending_action = None

        # Fast-path Media Controls & Global STOP Command Priority
        if self._handle_media_control_fastpath(cmd_lower):
            return True

        # Route slash commands
        if cmd_lower in ["/exit", "/quit", "exit", "quit", "bye"]:
            return self.cmd_exit()

        elif cmd_lower in ["/clear", "/cls", "clear", "cls"]:
            return self.cmd_clear()

        elif cmd_lower in ["/help", "help", "?"]:
            return self.cmd_help()

        elif cmd_lower in ["/status", "/sys", "/sysinfo", "status", "sysinfo"]:
            return self.cmd_status()

        elif cmd_lower in ["/voice", "voice"] or cmd_lower.startswith("/voice "):
            return self.cmd_voice(user_input)

        elif cmd_lower in ["/actions", "/automation", "automation"]:
            return self.cmd_automation()

        elif cmd_lower in ["/timers", "/tasks", "/schedule", "timers", "tasks", "schedule"]:
            return self.cmd_schedule()

        elif cmd_lower.startswith("/canceltimer") or cmd_lower.startswith("/canceltask"):
            return self.cmd_canceltimer(user_input)

        elif cmd_lower in ["/matrix", "matrix"]:
            return self.cmd_matrix()

        elif cmd_lower.startswith("/theme"):
            return self.cmd_theme(user_input)

        elif cmd_lower.startswith("/calc"):
            return self.cmd_calc(user_input)

        elif cmd_lower in ["/time", "/clock", "time", "clock"]:
            return self.cmd_time()

        elif cmd_lower in ["/history", "history"]:
            return self.cmd_history()

        elif cmd_lower in ["/about", "about"]:
            return self.cmd_about()

        elif cmd_lower in ["/debug", "/dev"]:
            return self.cmd_debug()

        # ── Coding Mode (Gemini) ────────────────────────────────
        elif cmd_lower in ["/code", "coding mode", "/gemini"] or cmd_lower.startswith("/code "):
            query = user_input[5:].strip() if cmd_lower.startswith("/code ") else ""
            return self.process_coding_query(query or "")

        # ── Memory commands ─────────────────────────────────────
        elif cmd_lower in ["/memory", "memory", "show memory"]:
            return self.cmd_memory()

        elif cmd_lower in ["/clearmemory", "clear memory", "forget everything", "wipe memory"]:
            return self.cmd_clearmemory()

        # ── WhatsApp Call Controls ──────────────────────────────────
        elif cmd_lower in ["end call", "hang up", "disconnect call"]:
            automation_engine.execute_action({"action": "end_call"}, confirmed=True)
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] Call ended.\n")
            voice_engine.speak("Call ended.")
            return True

        elif cmd_lower in ["answer call", "accept call"]:
            automation_engine.execute_action({"action": "answer_call"}, confirmed=True)
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] Incoming call answered.\n")
            voice_engine.speak("Incoming call answered.")
            return True

        elif cmd_lower in ["reject call", "decline call"]:
            automation_engine.execute_action({"action": "reject_call"}, confirmed=True)
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] Call declined.\n")
            voice_engine.speak("Call declined.")
            return True

        # ── API Configuration commands ──────────────────────────
        elif any(cmd_lower == phrase for phrase in [
            "configure api", "/configureapi", "/configure api", "api setup", "setup api"
        ]):
            return self.cmd_configure_api()

        elif any(cmd_lower == phrase for phrase in [
            "update groq api", "update groq key", "change groq key", "/updategroq"
        ]):
            return self.cmd_update_groq()

        elif any(cmd_lower == phrase for phrase in [
            "update gemini api", "update gemini key", "change gemini key", "/updategemini"
        ]):
            return self.cmd_update_gemini()

        elif any(cmd_lower == phrase for phrase in [
            "show api status", "api status", "/apistatus", "/api status"
        ]):
            return self.cmd_api_status()

        elif any(cmd_lower == phrase for phrase in [
            "disable groq", "remove groq key", "delete groq key"
        ]):
            return self.cmd_disable_groq()

        elif any(cmd_lower == phrase for phrase in [
            "disable gemini", "remove gemini key", "delete gemini key"
        ]):
            return self.cmd_disable_gemini()

        elif any(cmd_lower == phrase for phrase in [
            "reset api configuration", "reset api config", "reset api", "/resetapi"
        ]):
            return self.cmd_reset_api()

        elif cmd_lower in ["/clip", "/clipboard", "clipboard history", "show clipboard"]:
            return self.cmd_clipboard()

        elif cmd_lower in ["/windows", "list windows", "show windows", "what's open"]:
            return self.cmd_list_windows()

        elif cmd_lower in ["/prefs", "/preferences", "show preferences", "show memory", "my preferences", "what do you remember"]:
            return self.cmd_prefs()

        elif cmd_lower in ["/screen", "screen tools"]:
            return self.cmd_screen_info()

        elif cmd_lower in ["/processes", "/ps", "list processes", "show processes", "running processes"]:
            return self.cmd_list_processes()

        elif cmd_lower in ["/workspace", "/profile", "/workspaces", "workspace", "profiles"] or cmd_lower.startswith("/workspace ") or cmd_lower.startswith("/profile "):
            return self.cmd_workspace(user_input)

        elif cmd_lower in ["/tile", "tile windows", "tile all windows"]:
            return self.cmd_tile()

        elif any(cmd_lower == phrase for phrase in [
            "enable whatsapp auto send", "whatsapp auto send on", "enable whatsapp auto-send", "whatsapp auto-send on"
        ]):
            config.WHATSAPP_AUTO_SEND = True
            console.print("\n[bold green]✓ WhatsApp Auto Send ENABLED[/bold green]\n")
            voice_engine.speak("WhatsApp auto send enabled.")
            return True

        elif any(cmd_lower == phrase for phrase in [
            "disable whatsapp auto send", "whatsapp auto send off", "disable whatsapp auto-send", "whatsapp auto-send off"
        ]):
            config.WHATSAPP_AUTO_SEND = False
            console.print("\n[bold yellow]✓ WhatsApp Auto Send DISABLED (Safe Mode Active)[/bold yellow]\n")
            voice_engine.speak("WhatsApp auto send disabled.")
            return True

        elif any(cmd_lower == phrase for phrase in [
            "show automation settings", "automation settings", "/settings", "show settings"
        ]):
            return self.cmd_automation_settings()

        elif cmd_lower.startswith("/"):
            ui.print_error(f"Unknown command '{user_input}'. Type [bold white]/help[/bold white] for command matrix.")
            return True

        else:
            # Natural language pattern matching for common tasks
            # (before routing to LLM, handle obvious intents instantly)
            if self._handle_natural_language_shortcut(user_input, cmd_lower):
                return True

            # Real-Time Query Intent: online web search + Gemini summarizer
            import live_info
            if live_info.classify_query_intent(user_input) == "REAL_TIME_QUERY":
                live_info.handle_realtime_query(user_input, self.cli)
                return True

            # Auto-detect coding intent and route to Gemini if matched
            from gemini_engine import detect_coding_intent
            if detect_coding_intent(user_input):
                return self.process_coding_query(user_input)
            # Otherwise send query to Groq LLM Engine and Windows Automation Engine
            self.process_groq_llm_query(user_input)
            return True


    def cmd_debug(self):
        config.DEBUG_MODE = not config.DEBUG_MODE
        mode_str = "[bold green]ENABLED[/bold green]" if config.DEBUG_MODE else "[bold yellow]DISABLED[/bold yellow]"
        console.print(f"[dim cyan]● Developer Debug Mode {mode_str}[/dim cyan]\n")
        return True

    def cmd_exit(self):
        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
        console.print(f"\n[{t['accent']}][::] Powering down IRIS AI systems... Farewell. [::][/{t['accent']}]\n")
        voice_engine.stop_speech()
        return False

    def cmd_clear(self):
        console.clear()
        banner.render_banner(theme_key=self.cli.current_theme, animate=False)
        return True

    def cmd_help(self):
        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
        accent = t["accent"]

        # Table 1: Command Matrix
        table = Table(title="[bold cyan][::] IRIS AI COMMAND MATRIX [::][/bold cyan]", border_style=t["border"])
        table.add_column("Command", style=f"bold {accent}", no_wrap=True)
        table.add_column("Description", style="white")

        table.add_row("/help", "Display this command matrix overview.")
        table.add_row("/code", "Boot into Coding Mode (Gemini AI pair programmer).")
        table.add_row("/listen", "Toggle background wake-word listener ('Hey IRIS').")
        table.add_row("/clip", "View rolling clipboard history & restore entries.")
        table.add_row("/windows", "List all open visible windows on your PC.")
        table.add_row("/prefs", "Show stored preferences & bookmarked folders.")
        table.add_row("/memory", "Show persistent conversation memory stats.")
        table.add_row("/clearmemory", "Wipe stored conversation history.")
        table.add_row("/screen", "Display screenshot, screen recording, & OCR tools.")
        table.add_row("/processes, /ps", "List running processes & memory usage.")
        table.add_row("/automation, /actions", "View desktop automation handlers & capabilities.")
        table.add_row("/timers, /tasks", "View active timers and background scheduled tasks.")
        table.add_row("/canceltimer [id]", "Cancel a running timer or task (or 'all').")
        table.add_row("/status, /sys", "Show live CPU, RAM, and System telemetry dashboard.")
        table.add_row("/theme [name]", "Switch visual theme (emerald, jarvis, cyberpunk, matrix, solar).")
        table.add_row("/voice", "Check local voice-cloning status and reference audio file.")
        table.add_row("/matrix", "Launch digital rain cyber visualizer.")
        table.add_row("/calc [expr]", "Perform high-precision mathematical evaluation.")
        table.add_row("/time", "Show detailed UTC & local time telemetry.")
        table.add_row("/debug", "Toggle developer debug mode (live telemetry logs).")
        table.add_row("/history", "View recent query history log.")
        table.add_row("/clear", "Refresh terminal view and banner HUD.")
        table.add_row("/about", "IRIS AI core specifications and architecture.")
        table.add_row("/exit, quit", "Gracefully terminate IRIS AI session.")
        table.add_section()
        table.add_row("[bold magenta]configure api[/bold magenta]", "[magenta]Run the full API key setup wizard (Groq + Gemini).[/magenta]")
        table.add_row("[bold magenta]update groq api[/bold magenta]", "[magenta]Update only the Groq API key.[/magenta]")
        table.add_row("[bold magenta]update gemini api[/bold magenta]", "[magenta]Update only the Gemini API key (enables Coding Mode).[/magenta]")
        table.add_row("[bold magenta]show api status[/bold magenta]", "[magenta]Display which API keys are configured (keys masked).[/magenta]")
        table.add_row("[bold magenta]disable groq[/bold magenta]", "[magenta]Remove the stored Groq API key.[/magenta]")
        table.add_row("[bold magenta]disable gemini[/bold magenta]", "[magenta]Remove the stored Gemini API key (disables Coding Mode).[/magenta]")
        table.add_row("[bold magenta]reset api configuration[/bold magenta]", "[magenta]Clear ALL stored API keys from local config.[/magenta]")

        console.print(table)

        # Table 2: What You Can Say To IRIS (Natural Language Examples)
        nl_table = Table(
            title="\n[bold cyan][::] WHAT YOU CAN SAY TO IRIS (NATURAL LANGUAGE EXAMPLES) [::][/bold cyan]",
            border_style=t["border"]
        )
        nl_table.add_column("Example Prompt", style=f"bold {accent}")
        nl_table.add_column("Action / Result", style="white")

        nl_table.add_row('"Create 10 folders Day1 to Day10 on my Desktop"', "Batch folder creation (10 folders Day1..Day10)")
        nl_table.add_row('"Compress the Projects folder into a ZIP"', "ZIP compression of specified folder")
        nl_table.add_row('"Set VS Code on left side and Spotify on right side"', "Split screen layout & window snapping")
        nl_table.add_row('"Minimize Chrome" / "Maximize VS Code"', "Window state controls (minimize, maximize, restore, focus)")
        nl_table.add_row('"Run git status"', "PowerShell / CMD output execution (with confirmation)")
        nl_table.add_row('"Install numpy"', "Pip package installation in Python environment")
        nl_table.add_row('"Take a screenshot"', "Full screen capture saved to Pictures/Screenshots/")
        nl_table.add_row('"Read my clipboard"', "Displays current clipboard content")
        nl_table.add_row('"Remember my editor is VS Code"', "Saves key-value preference to config/preferences.json")
        nl_table.add_row('"Find all PDFs in Documents"', "Multi-criteria file search across system folders")
        nl_table.add_row('"/prefs"', "Shows all remembered preferences & bookmarked folders")
        nl_table.add_row('"/windows"', "Lists all open visible windows on your PC")
        nl_table.add_row('"/clip"', "Shows rolling clipboard history and recall options")

        console.print(nl_table)
        console.print(f"\n[{t['dim']}]Tip: Speak or type in natural language! IRIS automatically understands intent and executes actions.[/{t['dim']}]\n")
        return True

    def cmd_schedule(self):
        from task_scheduler import task_scheduler
        tasks = task_scheduler.get_active_tasks()
        ui.render_scheduled_tasks_table(tasks, theme_key=self.cli.current_theme)
        return True

    def cmd_canceltimer(self, command_str: str):
        parts = command_str.split(maxsplit=1)
        target_id = parts[1].strip() if len(parts) > 1 else None
        from task_scheduler import task_scheduler
        success, msg = task_scheduler.cancel_task(target_id)
        if success:
            console.print(f"[bold green]✓ {msg}[/bold green]\n")
            voice_engine.speak(msg)
        else:
            ui.print_error(msg)
        return True

    def cmd_automation(self):
        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
        actions = automation_engine.registry.list_actions()
        actions_str = ", ".join([f"`{a}`" for a in sorted(actions)])

        info_text = (
            f"### :: SECURE WINDOWS AUTOMATION ENGINE ::\n\n"
            f"IRIS AI can execute PC control actions safely using structured JSON payloads.\n\n"
            f"* **Active Handlers ({len(actions)}):** {actions_str}\n"
            f"* **Security Guard:** High-risk actions (`delete_item`, `run_command`, `system_power`) require explicit `[y/N]` confirmation.\n"
            f"* **Plugin Registry:** Modular extensibility enabled.\n"
        )
        console.print(Panel(info_text, border_style=t["border"], title=f"[{t['accent']}][AUTOMATION TELEMETRY][/{t['accent']}]"))
        return True

    def cmd_automation_settings(self):
        ws_status = "ENABLED (Immediate Send)" if getattr(config, "WHATSAPP_AUTO_SEND", True) else "DISABLED (Safe Mode - Confirms Every Message)"
        voice_status = "ENABLED" if getattr(config, "VOICE_ENABLED", True) else "DISABLED"
        rate_str = f"{getattr(config, 'SPEECH_RATE', 1.25)}x"
        short_resp = "ENABLED (Ultra-concise)" if getattr(config, "SPEAK_SHORT_RESPONSES_ONLY", True) else "DISABLED"

        info = (
            f"### :: IRIS AUTOMATION & MESSAGING SETTINGS ::\n\n"
            f"* **WhatsApp Auto Send:** `{ws_status}`\n"
            f"* **Voice Response:** `{voice_status}`\n"
            f"* **Speech Speed Rate:** `{rate_str}`\n"
            f"* **Concise Spoken Replies:** `{short_resp}`\n"
            f"* **High-Risk Safeguards:** `Active (File Deletion, Shell Commands, System Power)`\n\n"
            f"[dim]Commands to adjust settings:\n"
            f"  • enable whatsapp auto send / disable whatsapp auto send\n"
            f"  • /voice rate 1.25 / /voice toggle / /voice short on[/dim]"
        )
        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
        console.print(Panel(info, border_style=t["border"], title=f"[{t['accent']}][AUTOMATION SETTINGS][/{t['accent']}]"))
        return True

    def _handle_media_control_fastpath(self, cmd_lower: str) -> bool:
        """
        High-priority instant media control & global STOP command handler.
        Executes immediately without LLM delay and responds with ultra-short spoken phrases.
        """
        import random
        from spotify_automation import play_spotify

        # 1. Global STOP / PAUSE / SHUT UP / QUIET interrupt
        if cmd_lower in ["stop", "pause", "shut up", "quiet", "stop music", "pause music", "stop speaking", "halt", "hush"]:
            voice_engine.stop_speech()
            play_spotify("pause")
            reply = random.choice(["Paused.", "Music paused.", "Done.", "Stopped."])
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        # 2. PLAY / RESUME
        if cmd_lower in ["play", "resume", "play music", "resume music", "start music"]:
            voice_engine.stop_speech()
            play_spotify("resume")
            reply = random.choice(["Playing.", "Resuming.", "Music resumed."])
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        # 3. NEXT
        if cmd_lower in ["next", "next song", "next track", "skip", "skip song"]:
            voice_engine.stop_speech()
            play_spotify("next")
            reply = random.choice(["Next track.", "Skipped."])
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        # 4. PREVIOUS
        if cmd_lower in ["previous", "previous song", "prev", "prev song", "previous track"]:
            voice_engine.stop_speech()
            play_spotify("prev")
            reply = "Previous track."
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        # 5. MUTE
        if cmd_lower in ["mute", "mute volume", "mute sound", "sound off"]:
            voice_engine.stop_speech()
            automation_engine.execute_action({"action": "set_volume", "level": 0}, confirmed=True)
            reply = random.choice(["Muted.", "Sound off."])
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        # 6. UNMUTE
        if cmd_lower in ["unmute", "unmute volume", "sound on"]:
            voice_engine.stop_speech()
            automation_engine.execute_action({"action": "set_volume", "level": 50}, confirmed=True)
            reply = "Unmuted."
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        # 7. VOLUME UP
        if cmd_lower in ["volume up", "louder", "increase volume", "turn it up"]:
            voice_engine.stop_speech()
            automation_engine.execute_action({"action": "set_volume", "level": 80}, confirmed=True)
            reply = random.choice(["Volume increased.", "Volume up."])
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        # 8. VOLUME DOWN
        if cmd_lower in ["volume down", "quieter", "decrease volume", "turn it down"]:
            voice_engine.stop_speech()
            automation_engine.execute_action({"action": "set_volume", "level": 30}, confirmed=True)
            reply = random.choice(["Volume decreased.", "Volume down."])
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(f"[{t['accent']}]IRIS AI >[/{t['accent']}] {reply}\n")
            voice_engine.speak(reply)
            return True

        return False

    def cmd_voice(self, command_str: str = ""):
        try:
            parts = command_str.split(maxsplit=2)
            subcmd = parts[1].lower() if len(parts) > 1 else "status"

            if subcmd in ["on", "enable"]:
                config.set_config("VOICE_ENABLED", True)
                console.print("\n[bold green]✓ Voice response ENABLED[/bold green]\n")
                voice_engine.speak("Voice enabled.")
                return True
            elif subcmd in ["off", "disable"]:
                config.set_config("VOICE_ENABLED", False)
                voice_engine.stop_speech()
                console.print("\n[bold yellow]✓ Voice response DISABLED[/bold yellow]\n")
                return True
            elif subcmd in ["toggle"]:
                cur = config.get_config("VOICE_ENABLED", True)
                config.set_config("VOICE_ENABLED", not cur)
                state = "ENABLED" if not cur else "DISABLED"
                console.print(f"\n[bold green]✓ Voice response {state}[/bold green]\n")
                if not cur:
                    voice_engine.speak("Voice enabled.")
                return True
            elif subcmd in ["rate", "speed"]:
                if len(parts) > 2:
                    try:
                        r = float(parts[2])
                        config.set_config("VOICE_RATE", r)
                        config.set_config("SPEECH_RATE", r)
                        pct = int((r - 1.0) * 100)
                        config.set_config("EDGE_TTS_RATE", f"+{pct}%" if pct >= 0 else f"{pct}%")
                        config.set_config("PYTTSX3_WPM", int(175 * r))
                        console.print(f"\n[bold green]✓ Speech rate set to {r:.2f}x ({config.get_config('EDGE_TTS_RATE')})[/bold green]\n")
                        voice_engine.speak(f"Speech rate updated to {r:.2f}x.")
                        return True
                    except ValueError:
                        pass
                console.print(f"\n[dim cyan]Current Speech Rate: {config.get_config('VOICE_RATE', 1.20):.2f}x ({config.get_config('EDGE_TTS_RATE', '+20%')})[/dim cyan]")
                console.print("[dim]Usage: /voice rate 1.20  (set 1.20x speed)[/dim]\n")
                return True
            elif subcmd in ["short"]:
                if len(parts) > 2:
                    val = parts[2].lower()
                    setting = val in ["on", "true", "yes", "1"]
                else:
                    setting = not config.get_config("SHORT_REPLY_MODE", True)
                config.set_config("SHORT_REPLY_MODE", setting)
                config.set_config("SPEAK_SHORT_RESPONSES_ONLY", setting)
                st = "ENABLED" if setting else "DISABLED"
                console.print(f"\n[bold green]✓ Short Reply Mode {st}[/bold green]\n")
                return True

            voice_engine.scan_and_load_voice(verbose=False)
            voice_engine_mode = "Cloned Voice" if getattr(voice_engine, "cloning_active", False) else config.get_config("VOICE_MODE", "Neural Voice")

            v_rate = f"{float(config.get_config('VOICE_RATE', 1.20)):.2f}x"
            v_pitch = f"{float(config.get_config('VOICE_PITCH', 1.00)):.2f}" if str(config.get_config('VOICE_PITCH', '1.00')).replace('.', '', 1).isdigit() else str(config.get_config('VOICE_PITCH', '+0Hz'))
            v_vol = f"{int(float(config.get_config('VOICE_VOLUME', 1.00)) * 100)}%"
            v_expr = str(config.get_config("EXPRESSIVENESS", "Balanced")).capitalize()
            v_short = "ON" if config.get_config("SHORT_REPLY_MODE", True) else "OFF"
            v_auto = "ON" if config.get_config("AUTO_SPEAK", True) else "OFF"

            voice_info = (
                f"### :: VOICE SETTINGS ::\n\n"
                f"* **Voice Engine:** `{voice_engine_mode}`\n"
                f"* **Speech Rate:** `{v_rate}`\n"
                f"* **Pitch:** `{v_pitch}`\n"
                f"* **Volume:** `{v_vol}`\n"
                f"* **Expressiveness:** `{v_expr}`\n"
                f"* **Short Reply Mode:** `{v_short}`\n"
                f"* **Auto Speak:** `{v_auto}`\n"
                f"* **Status:** `Ready`\n"
            )
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(Panel(voice_info, border_style=t["border"], title=f"[{t['accent']}][VOICE CONFIGURATION][/{t['accent']}]"))
            return True
        except Exception as ex:
            if getattr(config, "DEBUG_MODE", False):
                console.print(f"[bold red]Voice settings error: {ex}[/bold red]")
            else:
                console.print("[bold yellow]Voice settings updated with defaults.[/bold yellow]")
            return True

    def cmd_status(self):
        banner.render_scifi_status_hud(state="IDLE", theme_key=self.cli.current_theme)
        return True

    def cmd_matrix(self):
        ui.print_matrix_rain(duration=3.5)
        banner.render_banner(theme_key=self.cli.current_theme, animate=False)
        return True

    def cmd_theme(self, command_str: str):
        parts = command_str.split(maxsplit=1)
        if len(parts) < 2:
            available = ", ".join([f"[bold cyan]{k}[/bold cyan]" for k in config.THEMES.keys()])
            console.print(f"Available themes: {available}")
            console.print("Usage: [bold white]/theme <name>[/bold white]")
            return True

        new_theme = parts[1].strip().lower()
        if new_theme in config.THEMES:
            self.cli.current_theme = new_theme
            console.clear()
            banner.render_banner(theme_key=self.cli.current_theme, animate=False)
            console.print(f"[bold green]+ Theme switched to {config.THEMES[new_theme]['name']}![/bold green]\n")
        else:
            ui.print_error(f"Invalid theme '{new_theme}'. Choose from: {', '.join(config.THEMES.keys())}")
        return True

    def cmd_calc(self, command_str: str):
        expr = command_str.replace("/calc", "", 1).strip()
        if not expr:
            console.print("Usage: [bold white]/calc <expression>[/bold white] (e.g. /calc 2**10 + sqrt(144))")
            return True

        safe_dict = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "pi": math.pi, "e": math.e, "pow": math.pow, "log": math.log,
            "factorial": math.factorial, "abs": abs, "round": round
        }
        try:
            res = eval(expr, {"__builtins__": None}, safe_dict)
            calc_text = f"```math\n{expr} = {res}\n```"
            console.print(Panel(calc_text, border_style="cyan", title="[bold cyan][CALCULATOR RESULT][/bold cyan]"))
            voice_engine.speak(f"The calculated result is {res}")
        except Exception as err:
            ui.print_error(f"Calculation error: {err}")
        return True

    def cmd_time(self):
        now = datetime.now()
        utc = datetime.utcnow()
        time_text = (
            f"### :: TIME TELEMETRY ::\n\n"
            f"* **Local Time:** `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"* **UTC Time:** `{utc.strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
            f"* **Unix Timestamp:** `{int(now.timestamp())}`\n"
        )
        console.print(Panel(time_text, border_style="cyan", title="[bold cyan][TIME TELEMETRY][/bold cyan]"))
        return True

    def cmd_history(self):
        if not self.history:
            console.print("[dim]No query history recorded yet.[/dim]\n")
            return True

        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
        table = Table(title="[bold cyan][::] COMMAND HISTORY LOG [::][/bold cyan]", border_style=t["border"])
        table.add_column("#", style="dim", no_wrap=True)
        table.add_column("Query / Command", style="white")

        for idx, item in enumerate(self.history[-15:], 1):
            table.add_row(str(idx), item)

        console.print(table)
        console.print()
        return True

    def cmd_configure_api(self):
        """Run the full API setup wizard for both Groq and Gemini."""
        from key_manager import run_setup_wizard
        run_setup_wizard(update_groq=True, update_gemini=True)
        # Reinitialize LLM engine with potentially new key
        from llm_engine import llm_engine
        llm_engine.api_key = None
        llm_engine.client  = None
        llm_engine.initialize_client()
        return True

    def cmd_update_groq(self):
        """Update only the Groq API key."""
        from key_manager import run_setup_wizard
        console.print("\n[bold cyan]  -- Update Groq API Key --[/bold cyan]")
        run_setup_wizard(update_groq=True, update_gemini=False)
        from llm_engine import llm_engine
        llm_engine.api_key = None
        llm_engine.client  = None
        llm_engine.initialize_client()
        return True

    def cmd_update_gemini(self):
        """Update only the Gemini API key."""
        from key_manager import run_setup_wizard
        console.print("\n[bold magenta]  -- Update Gemini API Key --[/bold magenta]")
        run_setup_wizard(update_groq=False, update_gemini=True)
        return True

    def cmd_api_status(self):
        """Display current API key configuration status (keys masked)."""
        from key_manager import print_api_status
        print_api_status(theme_key=self.cli.current_theme)
        return True

    def cmd_disable_groq(self):
        """Remove the stored Groq API key."""
        from key_manager import delete_groq_api_key
        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
        accent = t["accent"]
        console.print(f"\n[bold yellow]  [!!] This will remove your Groq API key.[/bold yellow]")
        console.print("  [dim]IRIS will not be able to process AI queries until a new key is added.[/dim]")
        try:
            confirm = input("  Type  YES  to confirm: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            confirm = ""
        if confirm == "YES":
            delete_groq_api_key()
            console.print("[bold yellow]  Groq API key removed. Run  update groq api  to add a new one.[/bold yellow]\n")
        else:
            console.print("[dim]  Cancelled.[/dim]\n")
        return True

    def cmd_disable_gemini(self):
        """Remove the stored Gemini API key (disables Coding Mode)."""
        from key_manager import delete_gemini_api_key
        delete_gemini_api_key()
        console.print("[bold yellow]  Gemini API key removed. Coding Mode is now disabled.[/bold yellow]")
        console.print("[dim]  Run  update gemini api  to re-enable Coding Mode.[/dim]\n")
        return True

    def cmd_reset_api(self):
        """Clear ALL stored API keys from config/config.json."""
        console.print("\n[bold red]  [!!] This will delete ALL stored API keys.[/bold red]")
        console.print("  [dim]IRIS will run the setup wizard on next launch.[/dim]")
        try:
            confirm = input("  Type  RESET  to confirm: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            confirm = ""
        if confirm == "RESET":
            from key_manager import reset_api_config
            reset_api_config()
        else:
            console.print("[dim]  Cancelled.[/dim]\n")
        return True

    def cmd_about(self):
        from key_manager import get_api_status, _mask
        api = get_api_status()
        gem_line = (
            f"`Gemini API (Coding Mode active)`"
            if api["gemini"]["configured"]
            else "`Gemini API (not configured — Coding Mode disabled)`"
        )
        about_text = (
            f"### :: ABOUT IRIS AI (JARVIS ARCHITECTURE) ::\n\n"
            f"**IRIS AI** is a production-ready, futuristic Sci-Fi CLI assistant integrated with Groq LLM reasoning, Windows Automation Engine, and local voice-cloning capabilities.\n\n"
            f"* **Primary LLM:** `Groq API ({llm_engine.model_name})`\n"
            f"* **Coding LLM:**  {gem_line}\n"
            f"* **Automation Engine:** `Active ({len(automation_engine.registry.list_actions())} handlers)`\n"
            f"* **Voice Cloning:** `Enabled (Cached speaker reference)`\n"
            f"* **Framework:** Python + Rich + Prompt Toolkit + PyFiglet + Groq\n"
        )
        console.print(Panel(about_text, border_style="cyan", title="[bold cyan][ABOUT IRIS AI][/bold cyan]"))
        return True


    def _classify_intent(self, query: str, action_data: dict | None) -> str:
        """Classify user request into structured Intent categories."""
        import live_info
        if live_info.classify_query_intent(query) == "REAL_TIME_QUERY":
            return "Real-Time Information Query"
        q_lower = query.lower()
        if any(w in q_lower for w in ["time", "clock", "date"]):
            return "Current Time"

        elif any(w in q_lower for w in ["news", "headline", "headlines"]):
            return "Current News"
        elif any(w in q_lower for w in ["weather", "temperature", "forecast"]):
            return "Current Information"

        if action_data:
            act = action_data.get("action", "").lower()
            if act in ["set_timer", "pause_timer", "resume_timer", "cancel_timer", "get_timer_status", "schedule_delayed_action", "schedule_recurring_task", "list_tasks", "reschedule_task"]:
                return "Task Scheduling / Timer"
            elif act in ["play_spotify", "media_play_pause", "media_next", "media_prev", "set_volume", "mute_audio", "unmute_audio"]:
                return "Media Control"
            elif act in ["send_message"]:
                return "Messaging"
            elif act in ["open_desktop_item", "search_files"]:
                return "File Search"
            elif act in ["open_website", "browser_action", "web_search"]:
                return "Browser Control"
            elif act in ["get_system_info", "open_settings", "set_brightness"]:
                return "System Control"
            elif act in ["open_app", "close_app", "create_file", "create_folder", "rename_item", "delete_item", "run_command", "system_power"]:
                return "Windows Automation"

        if any(w in q_lower for w in ["timer", "schedule", "remind", "reminder", "alarm"]):
            return "Task Scheduling / Timer"
        elif any(w in q_lower for w in ["play", "spotify", "song", "music", "volume"]):
            return "Media Control"
        elif any(w in q_lower for w in ["whatsapp", "telegram", "discord", "teams", "message", "send"]):
            return "Messaging"
        elif any(w in q_lower for w in ["search file", "find file", "desktop"]):
            return "File Search"
        elif any(w in q_lower for w in ["open app", "close", "shutdown", "restart"]):
            return "Windows Automation"

        return "General Knowledge"

    def process_groq_llm_query(self, query: str):
        """Streams real AI responses from Groq model and executes desktop automation intents safely."""
        self.chat_history.append({"role": "user", "content": query})

        # Step 1: Generate stream response from Groq LLM
        generator = llm_engine.stream_query(query, history=self.chat_history)

        # Step 2: Render streaming UI
        full_response = ui.render_streaming_response(
            generator,
            title="IRIS AI",
            theme_key=self.cli.current_theme,
            speak=True
        )

        if full_response and full_response.strip():
            self.chat_history.append({"role": "assistant", "content": full_response.strip()})
            self.chat_history = self.chat_history[-12:]

        # Step 3: Extract Action Intent
        action_intent = extract_action_intent(full_response)

        # Classify and Log Intent
        intent_cat = self._classify_intent(query, action_intent)
        if config.DEBUG_MODE:
            console.print(f"[bold cyan][INTENT] {intent_cat}[/bold cyan]")
        debug_log(f"Intent classified: {intent_cat}", category="INTENT")

        # Handle Live Info Intent (Time, Weather, News without browser)
        if action_intent and action_intent.get("action") == "get_live_info":
            info_type = action_intent.get("type", "time").lower()
            import live_info
            if "time" in info_type or "date" in info_type or "time" in query.lower():
                live_text = live_info.get_current_time()
            elif "weather" in info_type or "weather" in query.lower():
                live_text = live_info.get_live_weather()
            elif "news" in info_type or "news" in query.lower():
                live_text = live_info.get_live_news()
            else:
                live_text = live_info.get_current_time()

            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            console.print(Panel(live_text, border_style=t["border"], title=f"[{t['accent']}]✦ LIVE INFORMATION[/{t['accent']}]", padding=(0, 1)))
            voice_engine.speak(live_text, force_full=True)
            return

        # Direct Query checks for Time, Weather, News if LLM didn't output JSON
        q_lower = query.lower().strip()
        if "time" in q_lower and any(w in q_lower for w in ["what", "current", "tell"]):
            import live_info
            t_str = live_info.get_current_time()
            console.print(f"[bold green]{t_str}[/bold green]")
            voice_engine.speak(t_str)
            return
        elif "weather" in q_lower and any(w in q_lower for w in ["today", "what", "current", "tell"]):
            import live_info
            w_str = live_info.get_live_weather()
            console.print(f"[bold green]{w_str}[/bold green]")
            voice_engine.speak(w_str)
            return
        elif "news" in q_lower and any(w in q_lower for w in ["today", "latest", "top", "headlines"]):
            import live_info
            n_str = live_info.get_live_news()
            console.print(f"[bold green]{n_str}[/bold green]")
            voice_engine.speak(n_str, force_full=True)
            return

        # Step 4: Execute Validated Automation Action if present
        if action_intent:
            if action_intent.get("action") == "send_message":
                recip = action_intent.get("recipient") or action_intent.get("to") or ""
                msg = action_intent.get("message") or action_intent.get("text") or ""
                self._execute_whatsapp_send(recip, msg)
                return

            high_risk, risk_reason = automation_engine.is_high_risk(action_intent)

            if high_risk:
                self.pending_action = action_intent
                return

            exec_result = automation_engine.execute_action(action_intent, confirmed=True)

            # Telemetry logging & UI rendering
            ui.render_action_telemetry(exec_result, theme_key=self.cli.current_theme)

            # Trigger natural, concise spoken confirmation
            if exec_result.get("status") == "success":
                act = action_intent.get("action", "")
                tgt = action_intent.get("target") or action_intent.get("name") or action_intent.get("query") or ""
                voice_engine.speak_action_confirm(act, tgt)
            elif exec_result.get("status") == "failed":
                voice_engine.speak("Action could not be completed.")

    def _execute_whatsapp_send(self, contact: str, message: str) -> bool:
        """Execute or prompt WhatsApp message send based on WHATSAPP_AUTO_SEND config."""
        from automation.whatsapp import get_last_whatsapp_contact, set_last_whatsapp_contact

        target_contact = (contact or "").strip()
        if not target_contact or target_contact.lower() in ["contact", "last", "someone", "anyone"]:
            target_contact = get_last_whatsapp_contact()
            if not target_contact:
                ui.print_error("Please specify a contact to message.")
                return True
        else:
            set_last_whatsapp_contact(target_contact)

        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
        accent = t["accent"]
        auto_send_enabled = getattr(config, "WHATSAPP_AUTO_SEND", True)

        if not auto_send_enabled:
            # Safe Mode: Ask confirmation first
            self.pending_action = {
                "action": "send_message",
                "recipient": target_contact,
                "message": message,
                "app": "whatsapp"
            }
            console.print(f"[{accent}]IRIS AI > Send this message to {target_contact}?[/{accent}]\n")
            voice_engine.speak(f"Send this message to {target_contact}?")
            return True

        # Auto Send ON: Send immediately without confirmation prompt
        console.print(f"[{accent}]Sending to {target_contact}...[/{accent}]")

        res = automation_engine.execute_action({
            "action": "send_message",
            "recipient": target_contact,
            "message": message,
            "app": "whatsapp"
        }, confirmed=True)

        if res.get("status") == "success":
            console.print(f"[{accent}]IRIS AI >[/{accent}]\n[bold green]✓ Message sent.[/bold green]\n")
            voice_engine.speak("Message sent.")
        else:
            console.print(f"[{accent}]IRIS AI >[/{accent}]\n[bold red]Message failed.[/bold red]\n")
            voice_engine.speak("I couldn't send the message.")

        return True


    # =========================================================================
    # NEW COMMAND HANDLERS — Phase 5
    # =========================================================================

    def cmd_clipboard(self):
        """Show clipboard history."""
        from clipboard_engine import clipboard_engine
        clipboard_engine.print_history(theme_key=self.cli.current_theme)
        return True

    def cmd_list_windows(self):
        """List all open windows."""
        from window_manager import window_manager
        result = window_manager.list_open_windows()
        console.print(f"\n[bold cyan]{result}[/bold cyan]\n")
        return True

    def cmd_prefs(self):
        """Show stored preferences and bookmarked folders."""
        from memory import preference_store
        preference_store.print_all(theme_key=self.cli.current_theme)
        return True

    def cmd_screen_info(self):
        """Show screen engine capabilities."""
        console.print("\n[bold cyan][SCREEN ENGINE][/bold cyan]")
        console.print("  📷  take screenshot     → say 'take a screenshot'")
        console.print("  📐  area screenshot     → say 'capture area at x y width height'")
        console.print("  🎥  start recording     → say 'start screen recording'")
        console.print("  ⏹   stop recording      → say 'stop recording'")
        console.print("  🔍  OCR screen          → say 'read text on my screen'")
        console.print("[dim]  Screenshots → Pictures/Screenshots[/dim]")
        console.print("[dim]  Recordings → Videos/IRIS Recordings[/dim]\n")
        return True

    def cmd_list_processes(self):
        """List running processes."""
        from terminal_engine import terminal_engine
        result = terminal_engine.list_processes()
        console.print(f"\n[dim cyan]{result}[/dim cyan]\n")
        return True

    def _handle_natural_language_shortcut(self, user_input: str, cmd_lower: str) -> bool:
        """
        Fast-path NLP handler for very obvious intents that don't need LLM.
        Returns True if handled, False to let normal LLM routing continue.
        """
        # Priority 0: Browser Search Intent Fast-Path
        from automation.browser import parse_browser_search_query
        b_match = parse_browser_search_query(user_input)
        if b_match:
            engine, query_term = b_match
            t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
            accent = t["accent"]

            prov_display = "Stack Overflow" if engine == "stackoverflow" else ("YouTube" if engine == "youtube" else engine.title())

            # Execute browser search action
            res = automation_engine.execute_action({
                "action": "browser_search",
                "engine": engine,
                "query": query_term
            }, confirmed=True)

            msg = f"Searching {prov_display} for \"{query_term}\", Boss."
            console.print(f"[{accent}]IRIS AI >[/{accent}]\n{msg}\n")
            voice_engine.speak(f"Searching {prov_display} for {query_term}.")
            return True

        # WhatsApp Calling & Messaging Intent Priority Fast-Path
        if "whatsapp" in cmd_lower or any(w in cmd_lower for w in ["call ", "video call", "voice call", "ring "]):
            # Priority 1: Video Call
            if any(w in cmd_lower for w in ["video", "video call", "camera call", "facetime"]):
                contact = cmd_lower
                for prefix in ["open whatsapp and video call", "video call", "start a video call with", "start a video call", "on whatsapp", "whatsapp", "call"]:
                    contact = contact.replace(prefix, "")
                contact = contact.replace("and", "").replace("with", "").strip().title() or "contact"

                if config.get_config("DEBUG_MODE", False):
                    console.print("[bold cyan][INTENT] Detected Intent: video_call[/bold cyan]")

                t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
                console.print(f"[{t['accent']}]IRIS AI > Starting a video call with {contact}...[/{t['accent']}]")
                voice_engine.speak(f"Video calling {contact}.")

                res = automation_engine.execute_action({
                    "action": "whatsapp_call",
                    "recipient": contact,
                    "call_type": "video"
                }, confirmed=True)

                if res.get("status") == "success":
                    console.print(f"[{t['accent']}]✓ Video call started.[/{t['accent']}]\n")
                else:
                    console.print(f"[bold red]❌ {res.get('reason', 'I couldn\'t start the WhatsApp call.')}[/bold red]\n")
                return True

            # Priority 2: Voice Call
            elif any(w in cmd_lower for w in ["call", "voice call", "ring", "phone"]):
                contact = cmd_lower
                for prefix in ["open whatsapp and call", "whatsapp call", "voice call", "call", "ring", "phone", "on whatsapp", "whatsapp"]:
                    contact = contact.replace(prefix, "")
                contact = contact.replace("and", "").replace("with", "").strip().title() or "contact"

                if config.get_config("DEBUG_MODE", False):
                    console.print("[bold cyan][INTENT] Detected Intent: voice_call[/bold cyan]")

                t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])
                console.print(f"[{t['accent']}]IRIS AI > Calling {contact}...[/{t['accent']}]")
                voice_engine.speak(f"Calling {contact}.")

                res = automation_engine.execute_action({
                    "action": "whatsapp_call",
                    "recipient": contact,
                    "call_type": "voice"
                }, confirmed=True)

                if res.get("status") == "success":
                    console.print(f"[{t['accent']}]✓ Voice call started.[/{t['accent']}]\n")
                else:
                    console.print(f"[bold red]❌ {res.get('reason', 'I couldn\'t start the WhatsApp call.')}[/bold red]\n")
                return True

        # WhatsApp Messaging Intent Fast-Path & Follow-Up Contact Memory
        from automation.whatsapp import get_last_whatsapp_contact
        last_contact = get_last_whatsapp_contact()

        # Explicit send commands (e.g. "Send hello to Abdullah", "Send hello to GEMS SMP")
        if any(cmd_lower.startswith(p) for p in ["send ", "message ", "text ", "write to ", "whatsapp "]) and not any(w in cmd_lower for w in ["call", "video", "voice", "settings", "mode", "file", "folder"]):
            if " to " in cmd_lower:
                parts = user_input.split(" to ", 1)
                msg_part = parts[0]
                for p in ["send ", "message ", "text ", "write ", "whatsapp "]:
                    if msg_part.lower().startswith(p):
                        msg_part = msg_part[len(p):].strip()
                        break
                contact = parts[1].strip().title()
                msg = msg_part.strip()
                if contact and msg:
                    return self._execute_whatsapp_send(contact, msg)

        # Follow-up message commands when a last contact is remembered (e.g. "anyone want to play")
        if last_contact and not any(cmd_lower.startswith(p) for p in ["/", "open ", "close ", "play ", "search ", "what", "how", "who", "why", "where", "take ", "remember ", "forget "]):
            msg = user_input.strip()
            for p in ["send ", "tell ", "say "]:
                if msg.lower().startswith(p):
                    msg = msg[len(p):].strip()
                    break
            if msg and len(msg) > 1:
                return self._execute_whatsapp_send(last_contact, msg)

        # Clipboard quick reads
        if cmd_lower in ["what's on my clipboard", "read clipboard", "show clipboard", "clipboard"]:
            from clipboard_engine import clipboard_engine
            result = clipboard_engine.read()
            console.print(f"\n[bold cyan]{result}[/bold cyan]\n")
            return True

        # Preference memory
        if cmd_lower.startswith("remember ") and " is " in cmd_lower:
            from memory import preference_store
            # "Remember my editor is VS Code"  or  "Remember that X is Y"
            text = user_input[len("remember "):].strip()
            if " is " in text:
                parts = text.split(" is ", 1)
                key   = parts[0].replace("my ", "").replace("that ", "").strip()
                value = parts[1].strip()
                result = preference_store.remember(key, value)
                console.print(f"\n[bold green]{result}[/bold green]\n")
                return True

        if cmd_lower.startswith("forget "):
            from memory import preference_store
            key = user_input[len("forget "):].strip()
            result = preference_store.forget(key)
            console.print(f"\n[bold yellow]{result}[/bold yellow]\n")
            return True

        if cmd_lower.startswith("remember my") and "folder" in cmd_lower:
            # "Remember my projects folder is C:/Projects"
            from memory import preference_store
            text = user_input.lower()
            if " is " in text:
                before, path = user_input.split(" is ", 1)
                label = before.lower().replace("remember my", "").replace("folder", "").strip()
                result = preference_store.remember_folder(label, path.strip())
                console.print(f"\n[bold green]{result}[/bold green]\n")
                return True

        # Window Snapping NLP fast-path
        if ("left side" in cmd_lower or "right side" in cmd_lower or "left half" in cmd_lower or "right half" in cmd_lower or "snap " in cmd_lower) and any(kw in cmd_lower for kw in ["set ", "put ", "open ", "snap ", "move ", "place "]):
            from window_manager import window_manager
            side = "left" if "left" in cmd_lower else ("right" if "right" in cmd_lower else "left")
            target = ""
            for app in ["vs code", "vscode", "code", "spotify", "chrome", "edge", "notepad", "calculator", "discord", "steam", "explorer"]:
                if app in cmd_lower:
                    target = app
                    break
            if target:
                res = window_manager.snap_window(target, side)
                console.print(f"\n[bold cyan]{res}[/bold cyan]\n")
                voice_engine.speak(res)
                return True

        # Workspace Profiles NLP fast-path
        profile_matches = {
            "coding mode": "coding", "coding workspace": "coding",
            "study mode": "study", "study workspace": "study",
            "gaming mode": "gaming", "gaming workspace": "gaming",
            "movie mode": "movie", "cinema mode": "movie",
            "streaming mode": "streaming",
            "meeting mode": "meeting", "conference mode": "meeting"
        }
        for kw, prof in profile_matches.items():
            if kw in cmd_lower:
                from workspace_manager import workspace_manager
                res = workspace_manager.launch_profile(prof)
                console.print(f"\n[bold cyan]{res}[/bold cyan]\n")
                voice_engine.speak(f"Activated {prof.capitalize()} workspace profile.")
                return True

        if cmd_lower in ["tile windows", "tile all windows", "grid layout"]:
            from workspace_manager import workspace_manager
            res = workspace_manager.tile_all_windows()
            console.print(f"\n[bold cyan]{res}[/bold cyan]\n")
            return True

        return False

    def cmd_workspace(self, command_str: str = ""):
        parts = command_str.split(maxsplit=1)
        profile_name = parts[1].strip() if len(parts) > 1 else ""
        from workspace_manager import workspace_manager
        if not profile_name:
            console.print("\n[bold cyan][WORKSPACE PROFILES][/bold cyan]")
            console.print("  💻  Coding Mode     → say 'start coding mode' or '/workspace coding'")
            console.print("  📚  Study Mode      → say 'start study mode' or '/workspace study'")
            console.print("  🎮  Gaming Mode     → say 'start gaming mode' or '/workspace gaming'")
            console.print("  🎬  Movie Mode      → say 'start movie mode' or '/workspace movie'")
            console.print("  📡  Streaming Mode  → say 'start streaming mode' or '/workspace streaming'")
            console.print("  🎙  Meeting Mode    → say 'start meeting mode' or '/workspace meeting'")
            console.print("[dim]  Usage: /workspace [coding|study|gaming|movie|streaming|meeting][/dim]\n")
            return True
        res = workspace_manager.launch_profile(profile_name)
        console.print(f"\n[bold cyan]{res}[/bold cyan]\n")
        voice_engine.speak(f"Activated {profile_name} workspace profile.")
        return True

    def cmd_tile(self):
        from workspace_manager import workspace_manager
        res = workspace_manager.tile_all_windows()
        console.print(f"\n[bold cyan]{res}[/bold cyan]\n")
        return True

    # ── Coding Mode handler ───────────────────────────────────────────────────

    def process_coding_query(self, query: str = ""):
        """Route a coding question to Gemini Coding Engine and stream the response."""
        from gemini_engine import gemini_engine
        from key_manager import get_gemini_api_key

        t = config.THEMES.get(self.cli.current_theme, config.THEMES[config.DEFAULT_THEME])

        if not get_gemini_api_key():
            console.print(
                f"\n[bold magenta][GEMINI][/bold magenta] Coding Mode requires a Gemini API key.\n"
                "[dim]Run:  update gemini api  to add one.[/dim]\n"
                "[dim]Get a free key at: https://aistudio.google.com/app/apikey[/dim]\n"
            )
            return True

        if not query:
            console.print(f"\n[{t['accent']}]IRIS CODING MODE[/{t['accent']}] [dim](powered by Gemini)[/dim]")
            console.print("[dim]Ask any coding question, request code generation, or paste code to debug.[/dim]\n")
            try:
                query = input("Code query > ").strip()
            except (EOFError, KeyboardInterrupt):
                return True
            if not query:
                return True

        console.print(f"\n[bold magenta][GEMINI ⚡ CODING MODE][/bold magenta]\n")

        full_response = []
        try:
            for chunk in gemini_engine.stream_code_query(query):
                console.print(chunk, end="", markup=False)
                full_response.append(chunk)
        except Exception as ex:
            console.print(f"\n[bold red][GEMINI] Error: {ex}[/bold red]")

        console.print("\n")
        return True

    # ── Memory command handlers ──────────────────────────────────────────────

    def cmd_memory(self):
        from memory import memory_store
        memory_store.print_status(theme_key=self.cli.current_theme)
        return True

    def cmd_clearmemory(self):
        console.print("\n[bold yellow]⚠  This will delete ALL stored conversation history.[/bold yellow]")
        confirm = input("Type 'yes' to confirm: ").strip().lower()
        if confirm == "yes":
            from memory import memory_store
            memory_store.clear()
        else:
            console.print("[dim]  Memory clear cancelled.[/dim]\n")
        return True

    # ── Listen command handler ───────────────────────────────────────────────

    def cmd_listen(self):
        from wake_word import wake_word_listener
        if wake_word_listener.is_listening:
            wake_word_listener.stop()
            console.print("[bold yellow][WAKE] Wake word listener stopped.[/bold yellow]\n")
        else:
            started = wake_word_listener.start()
            if not started:
                console.print("[dim yellow]  Wake word unavailable — ensure SpeechRecognition and pyaudio are installed.[/dim yellow]\n")
        return True
