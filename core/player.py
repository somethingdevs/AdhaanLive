"""
Livestream playback using FFplay.
"""

import subprocess
import logging
from typing import Optional


def play_livestream(stream_url: str) -> Optional[subprocess.Popen]:
    """Start FFplay livestream playback."""
    if not stream_url:
        logging.error("[PLAY] No stream URL provided")
        return None

    cmd = [
        "ffplay",
        "-i", stream_url,
        "-loglevel", "error",
        "-autoexit"
    ]

    logging.info(f"[PLAY] Starting playback")

    try:
        proc = subprocess.Popen(cmd)
        return proc

    except FileNotFoundError:
        logging.error("[PLAY] ffplay not found (install FFmpeg)")
        return None

    except Exception as e:
        logging.error(f"[PLAY] Playback error: {e}")
        return None


def stop_livestream(process: Optional[subprocess.Popen]) -> None:
    """Stop FFplay playback."""
    if process:
        logging.info("[PLAY] Stopping playback")
        process.terminate()
