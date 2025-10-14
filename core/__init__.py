"""Initialize the core package and expose key functionality."""

from .detector import detect_audio_start, detect_audio_end
from .player import play_livestream, stop_livestream
from .scheduler import check_prayer_time
from .streamer import start_streamer

__all__ = [
    "detect_audio_start",
    "detect_audio_end",
    "play_livestream",
    "stop_livestream",
    "check_prayer_time",
    "start_streamer",
]
