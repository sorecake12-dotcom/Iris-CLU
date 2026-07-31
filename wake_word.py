"""
IRIS AI - Wake Word & Voice Input Module Stub
Preserved for modular compatibility. Microphone background listening is disabled.
"""

class WakeWordListenerStub:
    def __init__(self):
        self.is_listening = False
        self.mic_enabled = False
        self.is_sleeping = False
        self.current_status = "disabled"

    @staticmethod
    def is_available() -> bool:
        return False

    def start(self) -> bool:
        return False

    def stop(self):
        pass

    def get_status_badge(self) -> str:
        return "[dim red]🎤 Disabled[/dim red]"

    def wait_for_trigger(self, timeout: float = 0.05):
        return False, ""

    def capture_one_command(self) -> str:
        return ""


wake_word_listener = WakeWordListenerStub()
