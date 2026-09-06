"""
IRIS AI - WhatsApp Automation Facade
Re-exports clean API methods from the independent automation.whatsapp module.
"""

from automation.whatsapp import (
    open_messaging_app,
    automate_whatsapp_message,
    automate_whatsapp_call,
    end_whatsapp_call,
    answer_whatsapp_call,
    reject_whatsapp_call,
    send_whatsapp_message,
    bring_whatsapp_to_foreground,
    get_last_whatsapp_contact,
    set_last_whatsapp_contact,
)

__all__ = [
    "open_messaging_app",
    "automate_whatsapp_message",
    "automate_whatsapp_call",
    "end_whatsapp_call",
    "answer_whatsapp_call",
    "reject_whatsapp_call",
    "send_whatsapp_message",
    "bring_whatsapp_to_foreground",
    "get_last_whatsapp_contact",
    "set_last_whatsapp_contact",
]
