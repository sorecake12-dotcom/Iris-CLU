"""
IRIS AI - Spotify Automation Facade
Re-exports clean API methods from the independent automation.spotify module.
"""

from automation.spotify import (
    play_spotify,
    pause_spotify,
    resume_spotify,
    next_spotify_track,
    prev_spotify_track,
    toggle_spotify_shuffle,
    toggle_spotify_repeat,
    is_spotify_running,
    bring_spotify_to_foreground,
    ensure_spotify_open,
    fuzzy_match_song_name,
)

__all__ = [
    "play_spotify",
    "pause_spotify",
    "resume_spotify",
    "next_spotify_track",
    "prev_spotify_track",
    "toggle_spotify_shuffle",
    "toggle_spotify_repeat",
    "is_spotify_running",
    "bring_spotify_to_foreground",
    "ensure_spotify_open",
    "fuzzy_match_song_name",
]
