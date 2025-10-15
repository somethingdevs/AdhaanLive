"""
Adhaan event logger.
Logs Adhaan start and end times to a CSV file in /assets/adhaan_log.csv.
"""

import csv
import os
import threading
import logging
from datetime import datetime

# === Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "..", "assets", "adhaan_log.csv")
LOG_PATH = os.path.normpath(LOG_PATH)

# === Thread safety ===
_log_lock = threading.Lock()

# Track last start time in memory
_last_start_time = None


def _ensure_file_exists():
    """Ensure the CSV file and directory exist with headers."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "event", "stream_url", "duration_seconds"])
        logging.info(f"🗂️ Created new Adhaan log file at {LOG_PATH}")


def log_event(event: str, stream_url: str):
    """
    Log an Adhaan event to CSV.

    Args:
        event (str): 'start' or 'end'
        stream_url (str): the livestream URL where the event was detected
    """
    global _last_start_time
    _ensure_file_exists()
    timestamp = datetime.now()
    duration = None

    if event == "start":
        _last_start_time = timestamp
    elif event == "end" and _last_start_time:
        duration = (timestamp - _last_start_time).total_seconds()
        _last_start_time = None

    # Write to CSV
    with _log_lock:
        with open(LOG_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                event,
                stream_url,
                f"{duration:.1f}" if duration is not None else "",
            ])

    if duration is not None:
        logging.info(f"📝 Logged Adhaan END ({duration:.1f} sec)")
    else:
        logging.info(f"📝 Logged Adhaan {event.upper()} at {timestamp.strftime('%H:%M:%S')}")
