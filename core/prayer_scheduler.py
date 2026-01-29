import json
import logging
import time
from datetime import datetime, timedelta
import threading
import os

from core.detector import (
    start_audio_detection,
    stop_audio_detection,
    is_adhaan_active,
)
from core.playback import PLAYBACK
from utils.adhaan_logger import log_event

PRAYER_JSON_PATH = os.path.join("assets", "prayer_times.json")

WAKE_MINUTES_BEFORE = 10
TIMEOUT_MINUTES = 90
POST_CYCLE_COOLDOWN = 60


def load_prayer_times():
    if not os.path.exists(PRAYER_JSON_PATH):
        logging.warning("[SCHED] prayer_times.json missing")
        return {}

    try:
        with open(PRAYER_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[ERROR] Failed to load prayer times: {e}")
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
        except:
            continue

    if upcoming:
        return sorted(upcoming, key=lambda x: x[1])[0]

    # fallback = next day Fajr
    try:
        fajr_t = datetime.strptime(prayers["Fajr"], "%H:%M:%S").time()
        return "Fajr", datetime.combine(today + timedelta(days=1), fajr_t)
    except:
        return "Unknown", now + timedelta(hours=6)


def prayer_scheduler_loop(get_stream_url_fn, detection_flag):
    logging.info("[SCHED] Scheduler running")

    while True:
        try:
            prayers = load_prayer_times()
            if not prayers:
                logging.info("[SCHED] Waiting for prayer_times.json...")
                time.sleep(300)
                continue

            name, time_dt = get_next_prayer(prayers)
            wake_dt = time_dt - timedelta(minutes=WAKE_MINUTES_BEFORE)

            now = datetime.now()
            sleep_sec = max(0, (wake_dt - now).total_seconds())

            logging.info(f"[SCHED] Next={name} at {time_dt.time()} | waking at {wake_dt.time()}")
            log_event("sleep", "", 0, 0)
            detection_flag.clear()

            time.sleep(sleep_sec)

            stream_url = get_stream_url_fn()
            if not stream_url:
                logging.warning("[SCHED] No stream URL at wake; retrying in 60s")
                time.sleep(60)
                continue

            logging.info(f"[SCHED] Wake window for {name}")
            log_event("wake", "", 0, 0)

            # Wait until actual prayer time
            until_prayer = (time_dt - datetime.now()).total_seconds()
            if until_prayer > 0:
                time.sleep(until_prayer)

            # Start detection
            logging.info(f"[SCHED] Starting detection for {name}")
            start_audio_detection(stream_url)
            detection_flag.set()

            timeout_dt = time_dt + timedelta(minutes=TIMEOUT_MINUTES)

            while datetime.now() < timeout_dt:
                if is_adhaan_active():
                    logging.info(f"[SCHED] Adhaan detected for {name}")
                    break
                time.sleep(5)

            if not is_adhaan_active():
                logging.warning(f"[SCHED] No Adhaan detected for {name}")
                log_event("no_adhaan", "", 0, 0)
                stop_audio_detection()
                detection_flag.clear()

            while is_adhaan_active():
                time.sleep(3)

        except Exception as e:
            logging.error(f"[ERROR] Scheduler failure: {e}", exc_info=True)

        finally:
            stop_audio_detection()
            detection_flag.clear()

            PLAYBACK.stop()

            logging.info(f"[SCHED] {name} cycle complete")
            time.sleep(POST_CYCLE_COOLDOWN)


def start_prayer_scheduler(get_stream_url_fn, detection_flag):
    t = threading.Thread(
        target=prayer_scheduler_loop,
        args=(get_stream_url_fn, detection_flag),
        daemon=True,
    )
    t.start()
    logging.info("[SCHED] Scheduler started")
