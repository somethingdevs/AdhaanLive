"""
Adhaan event logger — CSV based.
"""

import csv
import os
import threading
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR.parent / "assets" / "adhaan_log.csv"

_log_lock = threading.Lock()
_last_start_time = None


def _ensure_file_exists():
    """Ensure CSV file exists with header."""
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
                "data_mb",
            ])
        logging.info(f"[LOG] Created adhaan_log.csv")


def log_event(event_type: str,
              snippet_path: str = None,
              rms: float = None,
              db: float = None,
              data_mb: float = None):
    """Append event row to CSV."""
    global _last_start_time
    _ensure_file_exists()

    timestamp = datetime.now()
    duration = None

    if event_type == "start":
        _last_start_time = timestamp

    elif event_type == "end" and _last_start_time:
        duration = (timestamp - _last_start_time).total_seconds()
        _last_start_time = None

    snippet_rel = os.path.basename(snippet_path) if snippet_path else ""

    # --- Write CSV ---
    with _log_lock:
        with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                event_type,
                snippet_rel,
                f"{rms:.6f}" if rms is not None else "",
                f"{db:.2f}" if db is not None else "",
                f"{duration:.1f}" if duration is not None else "",
                f"{data_mb:.2f}" if data_mb is not None else "",
            ])

    # --- Console logs (clean) ---
    if event_type == "start":
        logging.info(f"[LOG] START | file={snippet_rel} rms={rms:.6f} db={db:.2f}")

    elif event_type == "end":
        logging.info(
            f"[LOG] END   | file={snippet_rel} dur={duration:.1f}s "
            f"rms={rms:.6f} db={db:.2f}"
        )

    elif event_type in ("data_usage", "ambient_usage"):
        logging.debug(f"[LOG] DATA  | {event_type}={data_mb:.2f}MB")

    else:
        logging.info(f"[LOG] {event_type.upper()} | file={snippet_rel}")
