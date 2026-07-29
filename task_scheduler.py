"""
IRIS AI - Task Scheduler & Timer Engine
Provides background, thread-safe execution for timers, delayed actions, scheduled automations, and recurring reminders.
"""

import os
import re
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from debug_logger import debug_log, log_exception
from notifier import notify_timer_done, notify_reminder, notify_action_done

console = Console()

class TaskItem:
    """Represents a scheduled timer, delayed action, or recurring automation task."""

    def __init__(
        self,
        task_id: str,
        task_type: str,  # "timer", "delayed_action", "scheduled", "recurring"
        description: str,
        target_time: datetime,
        duration_seconds: float = 0.0,
        action_data: Optional[dict] = None,
        message: Optional[str] = None,
        recurrence: Optional[dict] = None,  # e.g., {"rule": "hourly"} or {"rule": "daily", "time": "19:00"}
        speak_on_finish: Optional[str] = None
    ):
        self.task_id = str(task_id)
        self.task_type = task_type
        self.description = description
        self.created_at = datetime.now()
        self.target_time = target_time
        self.duration_seconds = duration_seconds
        self.remaining_seconds_when_paused = 0.0
        self.action_data = action_data or {}
        self.message = message or description
        self.recurrence = recurrence or {}
        self.speak_on_finish = speak_on_finish
        self.status = "running"  # "running", "paused", "completed", "cancelled"

    def get_remaining_seconds(self) -> float:
        """Returns remaining seconds until execution."""
        if self.status == "paused":
            return max(0.0, self.remaining_seconds_when_paused)
        elif self.status == "running":
            delta = (self.target_time - datetime.now()).total_seconds()
            return max(0.0, delta)
        return 0.0

    def pause(self) -> bool:
        """Pause a running timer/task."""
        if self.status == "running":
            self.remaining_seconds_when_paused = self.get_remaining_seconds()
            self.status = "paused"
            return True
        return False

    def resume(self) -> bool:
        """Resume a paused timer/task."""
        if self.status == "paused":
            self.target_time = datetime.now() + timedelta(seconds=self.remaining_seconds_when_paused)
            self.status = "running"
            return True
        return False

    def cancel(self) -> bool:
        """Cancel task."""
        if self.status in ["running", "paused"]:
            self.status = "cancelled"
            return True
        return False

    def format_time_left(self) -> str:
        """Format time left nicely (e.g. '1 min 30 sec', '45 sec', '2 hrs')."""
        rem = self.get_remaining_seconds()
        if rem <= 0:
            return "0s"
        
        hours = int(rem // 3600)
        minutes = int((rem % 3600) // 60)
        seconds = int(rem % 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            "id": self.task_id,
            "type": self.task_type,
            "description": self.description,
            "status": self.status,
            "time_left": self.format_time_left(),
            "target_time": self.target_time.strftime("%Y-%m-%d %H:%M:%S")
        }


def parse_time_duration(text: str) -> Optional[float]:
    """
    Parses natural language duration expressions into total seconds.
    Examples:
        "2 minutes" -> 120.0
        "30 seconds" -> 30.0
        "1.5 hours" -> 5400.0
        "1 hour 30 mins" -> 5400.0
        "in 10 minutes" -> 600.0
        "after 2 minutes" -> 120.0
    """
    if not text:
        return None

    t_lower = text.lower()
    total_seconds = 0.0
    found_any = False

    # Hours
    hr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", t_lower)
    if hr_match:
        total_seconds += float(hr_match.group(1)) * 3600
        found_any = True

    # Minutes
    min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b", t_lower)
    if min_match:
        total_seconds += float(min_match.group(1)) * 60
        found_any = True

    # Seconds
    sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", t_lower)
    if sec_match:
        total_seconds += float(sec_match.group(1))
        found_any = True

    if found_any:
        return total_seconds

    # Fallback digit check if phrase is e.g. "for 5" (default to minutes or seconds depending on context)
    digit_match = re.search(r"\b(\d+)\b", t_lower)
    if digit_match:
        val = float(digit_match.group(1))
        if "sec" in t_lower:
            return val
        elif "hour" in t_lower:
            return val * 3600
        return val * 60  # default to minutes

    return None


def parse_clock_or_date(text: str) -> Optional[datetime]:
    """
    Parses exact clock times or date specifications.
    Examples:
        "at 9 AM" -> datetime for today/tomorrow at 09:00:00
        "at 7 PM" -> datetime for today/tomorrow at 19:00:00
        "tomorrow at 9 AM" -> datetime for tomorrow at 09:00:00
    """
    if not text:
        return None

    now = datetime.now()
    t_lower = text.lower()

    # Time pattern like 9 AM, 9:30 PM, 19:00
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t_lower)
    if not time_match:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2)) if time_match.group(2) else 0
    ampm = time_match.group(3)

    if ampm:
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if "tomorrow" in t_lower or target <= now:
        target += timedelta(days=1)

    return target


class TaskScheduler:
    """Thread-safe background scheduler for IRIS AI."""

    def __init__(self):
        self.tasks: Dict[str, TaskItem] = {}
        self.lock = threading.Lock()
        self.timer_counter = 1
        self.task_counter = 1
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the background scheduler loop."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            if config.DEBUG_MODE:
                console.print("[dim cyan][SCHEDULER] Background Task Engine active.[/dim cyan]")
            debug_log("Task Scheduler background worker started.", category="SCHEDULER")

    def stop(self):
        """Stop background worker loop."""
        self.running = False

    def _generate_timer_id(self) -> str:
        with self.lock:
            tid = f"timer_{self.timer_counter}"
            self.timer_counter += 1
            return tid

    def _generate_task_id(self) -> str:
        with self.lock:
            tid = f"task_{self.task_counter}"
            self.task_counter += 1
            return tid

    def create_timer(self, duration_seconds: float, label: Optional[str] = None) -> TaskItem:
        """Create a countdown timer."""
        tid = self._generate_timer_id()
        target_dt = datetime.now() + timedelta(seconds=duration_seconds)
        
        # Format speech announcement
        dur_mins = int(duration_seconds // 60)
        dur_secs = int(duration_seconds % 60)
        
        if dur_mins > 0 and dur_secs > 0:
            dur_str = f"{dur_mins}-minute {dur_secs}-second"
        elif dur_mins > 0:
            dur_str = f"{dur_mins}-minute" if dur_mins != 1 else "1-minute"
            if duration_seconds >= 3600:
                hrs = int(duration_seconds // 3600)
                dur_str = f"{hrs}-hour" if hrs == 1 else f"{hrs}-hour"
        else:
            dur_str = f"{dur_secs}-second"

        lbl = label or f"{dur_str} timer"
        speak_msg = f"Boss, your {dur_str} timer has finished."

        task = TaskItem(
            task_id=tid,
            task_type="timer",
            description=lbl,
            target_time=target_dt,
            duration_seconds=duration_seconds,
            message=speak_msg,
            speak_on_finish=speak_msg
        )

        with self.lock:
            self.tasks[tid] = task

        if config.DEBUG_MODE:
            console.print(f"[dim cyan][SCHEDULER] Created {lbl} (ID: {tid}, target: {target_dt.strftime('%H:%M:%S')})[/dim cyan]")
        debug_log(f"Created timer {tid}: {lbl}", category="SCHEDULER")

        return task

    def create_delayed_action(self, delay_seconds: float, action_data: dict, description: str) -> TaskItem:
        """Create a delayed automation task."""
        tid = self._generate_task_id()
        target_dt = datetime.now() + timedelta(seconds=delay_seconds)

        speak_msg = f"Your timer has finished. Executing {description} now."

        task = TaskItem(
            task_id=tid,
            task_type="delayed_action",
            description=description,
            target_time=target_dt,
            duration_seconds=delay_seconds,
            action_data=action_data,
            message=description,
            speak_on_finish=speak_msg
        )

        with self.lock:
            self.tasks[tid] = task

        if config.DEBUG_MODE:
            console.print(f"[dim cyan][SCHEDULER] Scheduled delayed action '{description}' in {delay_seconds}s (ID: {tid})[/dim cyan]")
        debug_log(f"Scheduled delayed action {tid}: {description}", category="SCHEDULER")

        return task

    def create_scheduled_task(self, target_dt: datetime, action_data: dict, description: str) -> TaskItem:
        """Create a one-time scheduled task for a specific target datetime."""
        tid = self._generate_task_id()
        delay_sec = max(0.0, (target_dt - datetime.now()).total_seconds())

        speak_msg = f"Scheduled task time reached. Executing {description} now."

        task = TaskItem(
            task_id=tid,
            task_type="scheduled",
            description=description,
            target_time=target_dt,
            duration_seconds=delay_sec,
            action_data=action_data,
            message=description,
            speak_on_finish=speak_msg
        )

        with self.lock:
            self.tasks[tid] = task

        if config.DEBUG_MODE:
            console.print(f"[dim cyan][SCHEDULER] Scheduled task '{description}' for {target_dt.strftime('%Y-%m-%d %H:%M:%S')} (ID: {tid})[/dim cyan]")
        debug_log(f"Scheduled task {tid}: {description}", category="SCHEDULER")

        return task

    def create_recurring_task(
        self,
        recurrence_rule: str,  # "hourly", "daily", "weekdays", "weekly"
        action_data: Optional[dict] = None,
        description: str = "",
        message: Optional[str] = None,
        time_of_day: Optional[str] = None
    ) -> TaskItem:
        """Create a recurring automation or reminder task."""
        tid = self._generate_task_id()
        now = datetime.now()

        rec_data = {"rule": recurrence_rule, "time": time_of_day}

        # Calculate initial target datetime
        if recurrence_rule == "hourly":
            target_dt = now + timedelta(hours=1)
        elif recurrence_rule in ["daily", "weekdays"]:
            if time_of_day:
                time_dt = parse_clock_or_date(f"at {time_of_day}") or (now + timedelta(days=1))
                target_dt = time_dt
            else:
                target_dt = now + timedelta(days=1)
        else:
            target_dt = now + timedelta(days=1)

        dur_sec = max(0.0, (target_dt - now).total_seconds())
        speak_msg = message or f"Reminder: {description}"

        task = TaskItem(
            task_id=tid,
            task_type="recurring",
            description=description or message or f"Recurring {recurrence_rule} task",
            target_time=target_dt,
            duration_seconds=dur_sec,
            action_data=action_data,
            message=message or description,
            recurrence=rec_data,
            speak_on_finish=speak_msg
        )

        with self.lock:
            self.tasks[tid] = task

        if config.DEBUG_MODE:
            console.print(f"[dim cyan][SCHEDULER] Created recurring task '{task.description}' ({recurrence_rule}, ID: {tid})[/dim cyan]")
        debug_log(f"Created recurring task {tid}: {task.description}", category="SCHEDULER")

        return task

    def pause_timer(self, task_id_or_query: Optional[str] = None) -> Tuple[bool, str]:
        """Pause a running timer/task."""
        with self.lock:
            target_task = self._find_task(task_id_or_query)
            if not target_task:
                return False, "No running timer found to pause."
            
            if target_task.pause():
                return True, f"Paused {target_task.description} (ID: {target_task.task_id})."
            return False, f"Task {target_task.task_id} is not in running state."

    def resume_timer(self, task_id_or_query: Optional[str] = None) -> Tuple[bool, str]:
        """Resume a paused timer/task."""
        with self.lock:
            target_task = self._find_task(task_id_or_query, allow_paused=True)
            if not target_task:
                return False, "No paused timer found to resume."

            if target_task.resume():
                return True, f"Resumed {target_task.description} (ID: {target_task.task_id}). Time left: {target_task.format_time_left()}."
            return False, f"Task {target_task.task_id} is not paused."

    def cancel_task(self, task_id_or_query: Optional[str] = None) -> Tuple[bool, str]:
        """Cancel a specific timer or scheduled task."""
        with self.lock:
            if not task_id_or_query or task_id_or_query.lower() in ["all", "all timers", "everything"]:
                return self._cancel_all_unlocked()

            target_task = self._find_task(task_id_or_query, allow_paused=True)
            if not target_task:
                return False, f"Could not find active timer or task matching '{task_id_or_query}'."

            target_task.cancel()
            return True, f"Cancelled {target_task.description} (ID: {target_task.task_id})."

    def cancel_all_timers(self) -> Tuple[bool, str]:
        """Cancel all active timers and tasks."""
        with self.lock:
            return self._cancel_all_unlocked()

    def _cancel_all_unlocked(self) -> Tuple[bool, str]:
        count = 0
        for task in self.tasks.values():
            if task.status in ["running", "paused"]:
                task.cancel()
                count += 1
        if count > 0:
            return True, f"Cancelled all {count} active timer(s) and scheduled task(s)."
        return False, "No active timers or tasks to cancel."

    def get_timer_time_left(self, task_id_or_query: Optional[str] = None) -> str:
        """Returns string representation of remaining time for active timer(s)."""
        with self.lock:
            active = [t for t in self.tasks.values() if t.status in ["running", "paused"]]
            if not active:
                return "You don't have any active timers."

            if task_id_or_query:
                target = self._find_task(task_id_or_query, allow_paused=True)
                if target:
                    status_str = " (paused)" if target.status == "paused" else ""
                    return f"Timer {target.description} has {target.format_time_left()} remaining{status_str}."
                return f"No active timer found matching '{task_id_or_query}'."

            # Return details for most recent active timer or summary if multiple
            if len(active) == 1:
                t = active[0]
                status_str = " (paused)" if t.status == "paused" else ""
                return f"Boss, your {t.description} has {t.format_time_left()} remaining{status_str}."
            else:
                lines = [f"• {t.description} (ID: {t.task_id}): {t.format_time_left()} left" for t in active]
                return f"Boss, you have {len(active)} active timers:\n" + "\n".join(lines)

    def reschedule_task(self, task_id_or_query: str, new_delay_seconds: float) -> Tuple[bool, str]:
        """Reschedule an existing task with a new duration/delay."""
        with self.lock:
            target = self._find_task(task_id_or_query, allow_paused=True)
            if not target:
                return False, f"Could not find task matching '{task_id_or_query}'."

            target.duration_seconds = new_delay_seconds
            target.target_time = datetime.now() + timedelta(seconds=new_delay_seconds)
            target.status = "running"
            return True, f"Rescheduled {target.description} (ID: {target.task_id}) to finish in {target.format_time_left()}."

    def get_active_tasks(self, filter_type: Optional[str] = None) -> List[TaskItem]:
        """Return list of currently active or paused tasks."""
        with self.lock:
            tasks = [t for t in self.tasks.values() if t.status in ["running", "paused"]]
            if filter_type:
                tasks = [t for t in tasks if t.task_type == filter_type]
            return sorted(tasks, key=lambda x: x.get_remaining_seconds())

    def _find_task(self, query: Optional[str], allow_paused: bool = False) -> Optional[TaskItem]:
        """Internal helper to locate task by ID, number, or name matching."""
        active = [t for t in self.tasks.values() if t.status == "running" or (allow_paused and t.status == "paused")]
        if not active:
            return None

        if not query or query.lower() in ["timer", "the timer", "current timer"]:
            return active[-1]  # default to latest created active timer

        q_clean = query.lower().strip().replace("#", "").replace("timer_", "").replace("task_", "")
        
        # Match by exact ID or ID suffix number
        for t in active:
            if t.task_id.lower() == query.lower() or t.task_id.endswith(q_clean):
                return t

        # Match by description substring
        for t in active:
            if q_clean in t.description.lower():
                return t

        return active[-1]

    def _worker_loop(self):
        """Background thread executing scheduled tasks when due."""
        if config.DEBUG_MODE:
            console.print("[dim cyan][SCHEDULER] Background worker loop running...[/dim cyan]")
        while self.running:
            try:
                time.sleep(0.5)

                due_tasks: List[TaskItem] = []

                with self.lock:
                    now = datetime.now()
                    for task in list(self.tasks.values()):
                        if task.status == "running":
                            if now >= task.target_time:
                                due_tasks.append(task)
                                if task.task_type == "recurring":
                                    self._advance_recurring_task(task)
                                else:
                                    task.status = "completed"

                if due_tasks:
                    for task in due_tasks:
                        t_dispatch = threading.Thread(
                            target=self._dispatch_task_completion_safely,
                            args=(task,),
                            daemon=True
                        )
                        t_dispatch.start()
            except Exception as e:
                log_exception(e, context="SCHEDULER_WORKER_LOOP")

    def _dispatch_task_completion_safely(self, task: TaskItem):
        """Executes task completion logic safely inside a background thread."""
        try:
            from voice_engine import voice_engine
            from automation_engine import automation_engine
            self._handle_task_completion(task, voice_engine, automation_engine)
        except Exception as ex:
            log_exception(ex, context="SCHEDULER_TASK_COMPLETION_DISPATCH")

    def _advance_recurring_task(self, task: TaskItem):
        """Calculates next run time for recurring tasks."""
        rule = task.recurrence.get("rule", "daily")
        now = datetime.now()

        if rule == "hourly":
            task.target_time = now + timedelta(hours=1)
        elif rule == "daily":
            task.target_time = now + timedelta(days=1)
        elif rule == "weekdays":
            next_dt = now + timedelta(days=1)
            while next_dt.weekday() >= 5:  # Saturday or Sunday
                next_dt += timedelta(days=1)
            task.target_time = next_dt
        else:
            task.target_time = now + timedelta(days=1)

    def _handle_task_completion(self, task: TaskItem, voice_engine, automation_engine):
        """Triggers audio beep, voice announcement, terminal display, and automation execution."""
        if config.DEBUG_MODE:
            console.print(f"[bold cyan][SCHEDULER] Task {task.task_id} ({task.description}) finished![/bold cyan]")
        debug_log(f"Task finished: {task.task_id} ({task.description})", category="SCHEDULER")

        # 1. Sound Notification (Synth Beep / Chime)
        try:
            if os.name == "nt":
                import winsound
                winsound.Beep(1400, 150)
                time.sleep(0.05)
                winsound.Beep(1800, 250)
            else:
                print("\a", end="", flush=True)
        except Exception:
            pass

        # 2. Windows Toast Notification
        try:
            if task.task_type == "timer":
                notify_timer_done(task.description)
            elif task.task_type == "recurring":
                notify_reminder(task.message or task.description)
            else:
                notify_action_done(task.description)
        except Exception:
            pass

        # 3. Terminal Visual Notification
        self._print_terminal_notification(task)

        # 4. Spoken Announcement via active voice engine
        speech_text = task.speak_on_finish or f"Boss, your timer for {task.description} has finished."
        
        # If task has associated automation action, execute it automatically
        if task.action_data:
            act_name = task.action_data.get("action", "")
            if config.DEBUG_MODE:
                console.print(f"[dim green][SCHEDULER] Auto-executing scheduled action: {act_name}[/dim green]")
            
            exec_res = automation_engine.execute_action(task.action_data, confirmed=True)
            
            if exec_res.get("status") == "success":
                if act_name == "play_spotify":
                    speech_text = f"Your timer has finished. Opening Spotify and playing your song now."
                elif act_name == "send_message":
                    speech_text = f"Your timer has finished. Sent your WhatsApp message as scheduled."
                else:
                    speech_text = f"Your timer has finished. Executed {task.description} successfully."
            else:
                speech_text = f"Your timer has finished, but the scheduled action encountered an issue: {exec_res.get('reason')}."

        voice_engine.speak(speech_text)

    def _print_terminal_notification(self, task: TaskItem):
        """Format clean notification panel in terminal."""
        t = config.THEMES.get(config.DEFAULT_THEME)
        accent = t["accent"] if t else "bold cyan"

        msg = (
            f"⏰ [bold green]TIMER / TASK COMPLETED[/bold green]\n"
            f"● [bold white]{task.description}[/bold white] (ID: `{task.task_id}`)\n"
            f"● Finished at: `{datetime.now().strftime('%H:%M:%S')}`"
        )
        console.print()
        console.print(Panel(msg, border_style="bright_green", title="[bold bright_green][:: SCHEDULER NOTIFICATION ::][/bold bright_green]", padding=(0, 1)))
        console.print()


# Global Singleton Task Scheduler Instance
task_scheduler = TaskScheduler()
