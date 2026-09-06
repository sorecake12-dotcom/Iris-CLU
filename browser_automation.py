"""
IRIS AI - Browser Automation Facade
Re-exports clean API methods from the independent automation.browser module.
"""

from automation.browser import (
    bring_browser_to_foreground,
    open_multiple_websites,
    browser_search,
    parse_browser_search_query,
    close_browser_target,
    execute_tab_action,
    restore_browser_session,
    fill_form_text,
)

__all__ = [
    "bring_browser_to_foreground",
    "open_multiple_websites",
    "browser_search",
    "parse_browser_search_query",
    "close_browser_target",
    "execute_tab_action",
    "restore_browser_session",
    "fill_form_text",
]
