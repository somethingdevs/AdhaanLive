# --- CLEAN, ULTRA-MINIMAL LOGGING VERSION OF main.py ---

import threading
import logging
import time
import os
import json
from datetime import datetime, timedelta

from utils.logger import setup_logging      # ← NEW
setup_logging()                             # ← NEW (activate global logging)

from utils.prayer_api import get_prayer_times
from utils.config_loader import load_config

from core.stream_refresher import smart_refresh_loop, CACHE_PATH
from core.prayer_scheduler import start_prayer_scheduler
from utils.livestream import get_new_url_func

from core.detector import start_audio_detection, stop_audio_detection
from core.playback import PLAYBACK


# GLOBAL FLAGS
stop_flag = threading.Event()
detection_active_flag = threading.Event()


def _read_cached_url() -> str:
    """Read current HLS URL from cache."""
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


# ========== HOURLY SYSTEM DIGEST ==========
def heartbeat_status(interval_minutes: int = 60):
    while not stop_flag.is_set():
        try:
            url = _read_cached_url()
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




# ...

def monitor_stream_updates(poll_interval: int = 5):
    """Watch current_stream.txt for token changes.

    If the URL changes while detection is running, restart detection on the
    new URL. If we're idle (no detection window), just reset audio and let
    the scheduler start detection at the next prayer.
    """
    logging.info("[STREAM] Watcher started")

    last_mtime, last_url = None, None
    cached_url = _read_cached_url()

    if cached_url:
        logging.info("[STREAM] Initial URL cached")
        last_url = cached_url
        try:
            last_mtime = os.path.getmtime(CACHE_PATH)
        except FileNotFoundError:
            last_mtime = None

    while not stop_flag.is_set():
        try:
            if os.path.exists(CACHE_PATH):
                mtime = os.path.getmtime(CACHE_PATH)

                if last_mtime is None or mtime != last_mtime:
                    with open(CACHE_PATH, "r") as f:
                        new_url = f.read().strip()

                    if new_url and new_url != last_url:
                        was_running = detection_active_flag.is_set()
                        logging.info(
                            f"[STREAM] URL token updated → resetting audio "
                            f"(detection_active={was_running})"
                        )

                        # stop current audio stack
                        stop_audio_detection()
                        PLAYBACK.stop()
                        time.sleep(1.0)

                        if was_running:
                            # We’re in an active detection window → restart
                            logging.info("[STREAM] Restarting detection on new URL")
                            start_audio_detection(new_url)
                            detection_active_flag.set()
                        else:
                            # Idle; scheduler will kick off detection later
                            logging.info("[STREAM] Detection idle; scheduler will start next window")

                        last_url = new_url
                    last_mtime = mtime

            time.sleep(poll_interval)

        except Exception as e:
            logging.error(f"[ERROR] Stream watcher failure: {e}")
            time.sleep(5)



# ========== DAILY PRAYER-TIME REFRESH ==========
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


# ========== STREAM REFRESHER THREAD ==========
def run_stream_refresher():
    try:
        smart_refresh_loop(get_new_url_func)
    except Exception as e:
        logging.error(f"[ERROR] Stream refresher crashed: {e}")


# ========== MAIN ==========
def main():
    logging.info("[CORE] AdhaanLive started")

    threading.Thread(target=run_stream_refresher, daemon=True).start()
    threading.Thread(target=monitor_stream_updates, daemon=True).start()
    threading.Thread(target=heartbeat_status, daemon=True).start()

    threading.Thread(
        target=start_prayer_scheduler,
        args=(_read_cached_url, detection_active_flag),
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
