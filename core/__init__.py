"""Initialize the core package and expose key functionality."""

from .detector import (
    start_audio_detection,
    stop_audio_detection,
    start_ambient_monitor,
    stop_ambient_monitor,
    get_ambient_snapshot,
)

from .playback import PlaybackManager

from .stream_refresher import smart_refresh_loop, CACHE_PATH

__all__ = [
    "start_audio_detection",
    "stop_audio_detection",
    "start_ambient_monitor",
    "stop_ambient_monitor",
    "get_ambient_snapshot",
    "PlaybackManager",
    "smart_refresh_loop",
    "CACHE_PATH",
]
