"""
Handles livestream playback using FFplay.
"""

import subprocess
import logging
from typing import Optional


def play_livestream(stream_url: str) -> Optional[subprocess.Popen]:
    """Plays the livestream via FFplay."""
    if not stream_url:
        logging.error("⚠️ No stream URL provided.")
        return None

    cmd = ["ffplay", "-i", stream_url, "-loglevel", "error", "-autoexit"]
    logging.info(f"🎥 Starting livestream: {stream_url}")

    try:
        process = subprocess.Popen(cmd)
        return process
    except FileNotFoundError:
        logging.error("❌ ffplay not found. Ensure FFmpeg is installed and in PATH.")
    except Exception as e:
        logging.exception(f"Error starting livestream: {e}")
    return None


def stop_livestream(process: Optional[subprocess.Popen]) -> None:
    """Stops the FFplay process."""
    if process:
        logging.info("🔇 Stopping livestream...")
        process.terminate()
