# --- CLEAN, ULTRA-MINIMAL LOGGING VERSION OF main.py ---
# FastAPI-enabled, no circular imports

import threading
import logging
import time
import json
from datetime import datetime, timedelta

import uvicorn

from utils.logger import setup_logging
setup_logging()

from utils.prayer_api import get_prayer_times
from utils.config_loader import load_config

from core.stream_refresher import (
    smart_refresh_loop,
    read_cached_url,
)
from core.prayer_scheduler import start_prayer_scheduler
from utils.livestream import get_new_url_func

from core.detector import start_audio_detection, stop_audio_detection
from core.playback import PLAYBACK

# 🔹 Global flags (shared safely)
from core.globals import stop_flag, detection_active_flag

# 🔹 FastAPI app
from api.app import app


# ================= FASTAPI THREAD =================
def start_api():
    logging.info("[API] FastAPI starting on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


# ================= HEARTBEAT =================
def heartbeat_status(interval_minutes: int = 60):
    while not stop_flag.is_set():
        try:
            url = read_cached_url()
            url_state = "OK" if url else "MISSING"

            logging.info("")
            logging.info("----- SYSTEM DIGEST -----")
            logging.info(f"[STATUS] Stream URL: {url_state}")
            logging.info(f"[STATUS] Detection running: {detection_active_flag.is_set()}")
            logging.info("-------------------------")
            logging.info("")

        except Exception as e:
            logging.error(f"[ERROR] Heartbeat failure: {e}")

        time.sleep(interval_minutes * 60)


# ================= STREAM WATCHER =================
def monitor_stream_updates(poll_interval: int = 5):
    logging.info("[STREAM] Watcher started")

    last_mtime, last_url = None, None
    cached_url = read_cached_url()

    if cached_url:
        logging.info("[STREAM] Initial URL cached")
        last_url = cached_url

    while not stop_flag.is_set():
        try:
            url = read_cached_url()
            if url and url != last_url:
                was_running = detection_active_flag.is_set()
                logging.info(
                    f"[STREAM] URL token updated → resetting audio "
                    f"(detection_active={was_running})"
                )

                stop_audio_detection()
                PLAYBACK.stop()
                time.sleep(1.0)

                if was_running:
                    logging.info("[STREAM] Restarting detection on new URL")
                    start_audio_detection(url)
                    detection_active_flag.set()
                else:
                    logging.info("[STREAM] Detection idle; scheduler will start next window")

                last_url = url

            time.sleep(poll_interval)

        except Exception as e:
            logging.error(f"[ERROR] Stream watcher failure: {e}")
            time.sleep(5)


# ================= PRAYER REFRESH =================
def prayer_refresh_loop():
    cfg = load_config()
    city, country, method = (
        cfg["settings"]["city"],
        cfg["settings"]["country"],
        cfg["settings"]["method"],
    )

    while not stop_flag.is_set():
        try:
            logging.info(f"[SCHED] Refreshing prayer times ({city}, {country})")
            times = get_prayer_times(city, country, method)

            if times:
                with open("assets/prayer_times.json", "w", encoding="utf-8") as f:
                    json.dump({k: str(v) for k, v in times.items()}, f, indent=2)
                logging.info("[SCHED] Updated")
            else:
                logging.warning("[SCHED] Prayer API returned no data")

        except Exception as e:
            logging.error(f"[ERROR] Prayer refresh failure: {e}")

        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        time.sleep((next_midnight - now).total_seconds())


# ================= STREAM REFRESHER =================
def run_stream_refresher():
    try:
        smart_refresh_loop(get_new_url_func)
    except Exception as e:
        logging.error(f"[ERROR] Stream refresher crashed: {e}")


# ================= MAIN =================
def main():
    logging.info("[CORE] AdhaanLive started")

    # 🔹 Start FastAPI
    threading.Thread(target=start_api, daemon=True).start()

    # 🔹 Core threads
    threading.Thread(target=run_stream_refresher, daemon=True).start()
    threading.Thread(target=monitor_stream_updates, daemon=True).start()
    threading.Thread(target=heartbeat_status, daemon=True).start()

    threading.Thread(
        target=start_prayer_scheduler,
        args=(read_cached_url, detection_active_flag),
        daemon=True,
    ).start()

    threading.Thread(target=prayer_refresh_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("[CORE] Shutdown requested")

        stop_flag.set()
        stop_audio_detection()
        PLAYBACK.stop()

        logging.info("[CORE] AdhaanLive closed")


if __name__ == "__main__":
    main()
