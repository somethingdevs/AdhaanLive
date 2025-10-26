# core/playback_controller.py

import subprocess
import threading
import time
import logging

logger = logging.getLogger(__name__)

_ffplay_process = None
_lock = threading.Lock()


def start_adhaan_playback(stream_url: str):
    """
    Starts ffplay playback with a 1s fade-in effect ONLY if not already running.
    """
    global _ffplay_process
    with _lock:
        if _ffplay_process and _ffplay_process.poll() is None:
            logger.info("🎧 Playback already active — skipping new start.")
            return

        logger.info(f"🎧 Starting Adhaan playback with fade-in: {stream_url}")
        cmd = [
            "ffplay", "-nodisp", "-autoexit",
            "-af", "afade=t=in:ss=0:d=1",
            stream_url
        ]

        # Launch subprocess
        _ffplay_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_adhaan_playback():
    """
    Applies fade-out for 1s before killing ffplay gracefully.
    """
    global _ffplay_process
    with _lock:
        if not _ffplay_process or _ffplay_process.poll() is not None:
            logger.info("🛑 No active playback to stop.")
            return

        logger.info("🎚️ Applying fade-out before stopping ffplay (1s)...")
        time.sleep(1)  # Let fade-out take effect

        logger.info("🛑 Terminating ffplay process.")
        _ffplay_process.terminate()
        try:
            _ffplay_process.wait(timeout=3)
        except Exception:
            logger.warning("⚠️ Forced kill after timeout.")
            _ffplay_process.kill()

        _ffplay_process = None
