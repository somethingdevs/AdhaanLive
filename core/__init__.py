"""Initialize the core package and expose key functionality."""

from .detector import (
    detect_audio_start,
    detect_audio_end,
    start_audio_detection,
    stop_audio_detection,
    start_ambient_monitor,
    stop_ambient_monitor,
)
from .player import play_livestream, stop_livestream
from .scheduler import check_prayer_time
from .streamer import start_streamer
from .playback import start_buffered_playback, stop_buffered_playback

__all__ = [
    "detect_audio_start",
    "detect_audio_end",
    "start_audio_detection",
    "stop_audio_detection",
    "start_ambient_monitor",
    "stop_ambient_monitor",
    "play_livestream",
    "stop_livestream",
    "check_prayer_time",
    "start_streamer",
    "start_buffered_playback",
    "stop_buffered_playback",
]
