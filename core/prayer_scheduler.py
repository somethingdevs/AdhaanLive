# =====================================
# prayer_scheduler.py — STATE-CENTRALIZED
# =====================================

import json
import logging
import time
import threading
import os
from datetime import datetime, time as datetime_time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from core.detector import start_audio_detection, stop_audio_detection
from core.runtime_state import state
from utils.adhaan_logger import log_event

PRAYER_JSON_PATH = os.path.join("assets", "prayer_times.json")

WAKE_MINUTES_BEFORE = 10
TIMEOUT_MINUTES = 90
POST_CYCLE_COOLDOWN = 60
SCHEDULE_RECHECK_SECONDS = 60


# -------------------------------------
# Prayer time helpers
# -------------------------------------

def load_prayer_times() -> dict:
    if not os.path.exists(PRAYER_JSON_PATH):
        logging.warning("[SCHED] prayer_times.json missing")
        return {}

    try:
        with open(PRAYER_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[SCHED] Failed to load prayer times: {e}")
        return {}


def get_next_prayer(schedule: dict, now: Optional[datetime] = None):
    """Return the next absolute prayer instant from a structured schedule."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    prayers = schedule.get("prayers", {})
    if not isinstance(prayers, dict):
        return None, None

    upcoming = []

    for name, timestamp in prayers.items():
        try:
            prayer_dt = datetime.fromisoformat(timestamp)
            if prayer_dt.tzinfo is None:
                continue
            if prayer_dt > now:
                upcoming.append((name, prayer_dt))
        except (TypeError, ValueError):
            continue

    if upcoming:
        return sorted(upcoming, key=lambda x: x[1])[0]
    return None, None


def get_prayer_window(prayer_dt: datetime):
    """Return the detection wake time and hard timeout for a prayer."""
    return (
        prayer_dt - timedelta(minutes=WAKE_MINUTES_BEFORE),
        prayer_dt + timedelta(minutes=TIMEOUT_MINUTES),
    )


def seconds_until_mosque_midnight(
    timezone_name: str,
    now: Optional[datetime] = None,
) -> float:
    """Return seconds until the next midnight in the mosque's timezone."""
    reference_now = now or datetime.now(timezone.utc)
    if reference_now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    mosque_zone = ZoneInfo(timezone_name)
    mosque_now = reference_now.astimezone(mosque_zone)
    next_date = mosque_now.date() + timedelta(days=1)
    next_midnight = datetime.combine(
        next_date,
        datetime_time.min,
        tzinfo=mosque_zone,
    )
    return max(
        0,
        (
            next_midnight.astimezone(timezone.utc)
            - reference_now.astimezone(timezone.utc)
        ).total_seconds(),
    )


# -------------------------------------
# Scheduler core loop
# -------------------------------------

def _scheduler_loop(get_stream_url_fn):
    logging.info("[SCHED] Scheduler running")

    while True:
        name = "Unknown"

        try:
            prayers = load_prayer_times()
            if not prayers:
                logging.info("[SCHED] Waiting for prayer times...")
                time.sleep(300)
                continue

            name, prayer_dt = get_next_prayer(prayers)
            if not name or not prayer_dt:
                logging.info("[SCHED] No remaining prayer in current schedule")
                time.sleep(SCHEDULE_RECHECK_SECONDS)
                continue

            wake_dt, timeout_dt = get_prayer_window(prayer_dt)

            sleep_sec = max(
                0,
                (wake_dt - datetime.now(timezone.utc)).total_seconds(),
            )
            logging.info(
                "[SCHED] Next=%s at %s | waking at %s",
                name,
                prayer_dt.isoformat(),
                wake_dt.isoformat(),
            )

            log_event("sleep")
            time.sleep(sleep_sec)

            # -----------------------------
            # Wake window
            # -----------------------------
            stream_url = get_stream_url_fn()
            if not stream_url:
                logging.warning("[SCHED] No stream URL; retrying in 60s")
                time.sleep(60)
                continue

            log_event("wake")
            logging.info(f"[SCHED] Wake window for {name}")

            # Wait until exact prayer time
            until_prayer = max(
                0,
                (prayer_dt - datetime.now(timezone.utc)).total_seconds(),
            )
            time.sleep(until_prayer)

            # -----------------------------
            # Start detection
            # -----------------------------
            logging.info(f"[SCHED] Starting detection for {name}")
            start_audio_detection(stream_url)

            # Wait for adhaan or timeout
            while datetime.now(timezone.utc) < timeout_dt:
                if state.adhaan_active:
                    logging.info(f"[SCHED] Adhaan detected for {name}")
                    break
                time.sleep(5)

            if not state.adhaan_active:
                logging.warning(f"[SCHED] No Adhaan detected for {name}")
                log_event("no_adhaan")
                stop_audio_detection()

            # Wait until adhaan completes naturally
            while state.adhaan_active:
                time.sleep(3)

        except Exception:
            logging.error("[SCHED] Scheduler failure", exc_info=True)

        finally:
            stop_audio_detection()
            state.reset_cycle()

            logging.info(f"[SCHED] {name} cycle complete")
            time.sleep(POST_CYCLE_COOLDOWN)


# -------------------------------------
# Public API
# -------------------------------------

def start_prayer_scheduler(get_stream_url_fn):
    t = threading.Thread(
        target=_scheduler_loop,
        args=(get_stream_url_fn,),
        daemon=True,
    )
    t.start()
    logging.info("[SCHED] Scheduler started")
