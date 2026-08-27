import threading
import logging
import time
import json
from pathlib import Path

import uvicorn

from utils.logger import setup_logging
from utils.prayer_api import get_prayer_times
from utils.config_loader import PrayerSettings, load_prayer_settings
from utils.livestream import get_new_url_func

from api.app import app

from core.stream_refresher import start_stream_refresher
from core.prayer_scheduler import (
    seconds_until_mosque_midnight,
    start_prayer_scheduler,
)
from core.runtime_state import state

PRAYER_JSON_PATH = Path("assets/prayer_times.json")
PRAYER_REFRESH_RETRY_SECONDS = 5 * 60

# FastAPI
def start_api():
    logging.info("[API] FastAPI starting on port 8000")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=False,
    )

# Prayer time refresh job
def write_prayer_schedule(
    schedule: dict,
    schedule_path: Path = PRAYER_JSON_PATH,
) -> None:
    """Atomically persist a complete schedule for concurrent readers."""
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = schedule_path.with_suffix(schedule_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(schedule, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(schedule_path)


def refresh_prayer_schedule(
    settings: PrayerSettings,
    schedule_path: Path = PRAYER_JSON_PATH,
) -> bool:
    """Fetch and persist today's schedule, returning whether it succeeded."""
    try:
        logging.info(
            "[SCHED] Refreshing prayer times (%s, %s, %s)",
            settings.city,
            settings.country,
            settings.timezone,
        )
        schedule = get_prayer_times(settings)
        if not schedule:
            logging.warning("[SCHED] Prayer API returned no data")
            return False

        write_prayer_schedule(schedule, schedule_path)
        logging.info(
            "[SCHED] Prayer times updated for %s (%s)",
            schedule["date"],
            schedule["timezone"],
        )
        return True
    except Exception:
        logging.error("[SCHED] Prayer refresh failed", exc_info=True)
        return False


def prayer_refresh_loop(
    settings: PrayerSettings,
    refresh_immediately: bool = True,
) -> None:
    """Refresh at mosque midnight, retrying transient failures sooner."""
    if not refresh_immediately:
        time.sleep(seconds_until_mosque_midnight(settings.timezone))

    while True:
        succeeded = refresh_prayer_schedule(settings)
        delay = (
            seconds_until_mosque_midnight(settings.timezone)
            if succeeded
            else PRAYER_REFRESH_RETRY_SECONDS
        )
        time.sleep(delay)



def main():
    setup_logging()
    logging.info("[CORE] AdhaanLive started")

    prayer_settings = load_prayer_settings()
    initial_schedule_loaded = refresh_prayer_schedule(prayer_settings)

    # --- API ---
    threading.Thread(
        target=start_api,
        daemon=True,
    ).start()

    # --- Stream refresher ---
    stream_refresher = start_stream_refresher(get_new_url_func)

    # --- Prayer scheduler ---
    start_prayer_scheduler(stream_refresher.get_stream_url)

    # --- Prayer time refresh ---
    threading.Thread(
        target=prayer_refresh_loop,
        args=(prayer_settings, not initial_schedule_loaded),
        daemon=True,
    ).start()

    # --- Idle loop ---
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("[CORE] Shutdown requested")

        state.shutdown()

        logging.info("[CORE] AdhaanLive stopped")

if __name__ == "__main__":
    main()
