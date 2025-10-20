"""
Adhaan event logger.
Logs Adhaan start/end events, including audio metrics and saved snippet info.
Creates /assets/adhaan_log.csv if missing.
"""

import csv
import os
import threading
import logging
from datetime import datetime
from pathlib import Path

# === Paths ===
BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR.parent / "assets" / "adhaan_log.csv"

# === Thread safety ===
_log_lock = threading.Lock()
_last_start_time = None


def _ensure_file_exists():
    """Ensure the CSV log file and directory exist with headers."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        with open(LOG_PATH, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "event",
                "snippet_path",
                "rms",
                "db",
                "duration_seconds",
            ])
        logging.info(f"🗂️ Created new Adhaan log file at {LOG_PATH}")


def log_event(event_type: str,
              snippet_path: str = None,
              rms: float = None,
              db: float = None):
    """
    Logs Adhaan event details to CSV.

    Args:
        event_type (str): 'start' or 'end'
        snippet_path (str): path to saved audio snippet file (optional)
        rms (float): root-mean-square amplitude
        db (float): decibel level (dBFS)
    """
    global _last_start_time
    _ensure_file_exists()
    timestamp = datetime.now()
    duration = None

    if event_type == "start":
        _last_start_time = timestamp
    elif event_type == "end" and _last_start_time:
        duration = (timestamp - _last_start_time).total_seconds()
        _last_start_time = None

    # Normalize snippet path for CSV readability
    snippet_rel = os.path.basename(snippet_path) if snippet_path else ""

    with _log_lock:
        with open(LOG_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                event_type,
                snippet_rel,
                f"{rms:.6f}" if rms is not None else "",
                f"{db:.2f}" if db is not None else "",
                f"{duration:.1f}" if duration is not None else "",
            ])

    # Pretty console log
    if duration is not None:
        logging.info(f"📝 Logged END | Duration: {duration:.1f}s | RMS: {rms:.6f} | dB: {db:.2f} | File: {snippet_rel}")
    else:
        logging.info(f"📝 Logged {event_type.upper()} | RMS: {rms:.6f} | dB: {db:.2f} | File: {snippet_rel}")
