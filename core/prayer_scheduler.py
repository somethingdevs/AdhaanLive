# =====================================
# prayer_scheduler.py — STATE-CENTRALIZED
# =====================================

import json
import logging
import time
import threading
import os
from datetime import datetime, timedelta

from core.detector import start_audio_detection, stop_audio_detection
from core.runtime_state import state
from utils.adhaan_logger import log_event

PRAYER_JSON_PATH = os.path.join("assets", "prayer_times.json")

WAKE_MINUTES_BEFORE = 10
TIMEOUT_MINUTES = 90
POST_CYCLE_COOLDOWN = 60


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


def get_next_prayer(prayers: dict):
    now = datetime.now()
    today = now.date()
    upcoming = []

    for name, t_str in prayers.items():
        try:
            t = datetime.strptime(t_str, "%H:%M:%S").time()
            dt = datetime.combine(today, t)
            if dt > now:
                upcoming.append((name, dt))
        except Exception:
            continue

    if upcoming:
        return sorted(upcoming, key=lambda x: x[1])[0]

    # fallback → next day Fajr
    try:
        fajr_time = datetime.strptime(prayers["Fajr"], "%H:%M:%S").time()
        return "Fajr", datetime.combine(today + timedelta(days=1), fajr_time)
    except Exception:
        return "Unknown", now + timedelta(hours=6)


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
            wake_dt = prayer_dt - timedelta(minutes=WAKE_MINUTES_BEFORE)

            sleep_sec = max(0, (wake_dt - datetime.now()).total_seconds())
            logging.info(
                f"[SCHED] Next={name} at {prayer_dt.time()} | waking at {wake_dt.time()}"
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
                0, (prayer_dt - datetime.now()).total_seconds()
            )
            time.sleep(until_prayer)

            # -----------------------------
            # Start detection
            # -----------------------------
            logging.info(f"[SCHED] Starting detection for {name}")
            start_audio_detection(stream_url)

            timeout_dt = prayer_dt + timedelta(minutes=TIMEOUT_MINUTES)

            # Wait for adhaan or timeout
            while datetime.now() < timeout_dt:
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
