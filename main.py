import threading
import logging
import time
import json
import os
from datetime import datetime, timedelta

import uvicorn

from utils.logger import setup_logging
from utils.prayer_api import get_prayer_times
from utils.config_loader import load_config
from utils.livestream import get_new_url_func

from api.app import app

from core.stream_refresher import start_stream_refresher
from core.prayer_scheduler import start_prayer_scheduler
from core.runtime_state import state

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
def prayer_refresh_loop():
    cfg = load_config()
    city = cfg["settings"]["city"]
    country = cfg["settings"]["country"]
    method = cfg["settings"]["method"]

    os.makedirs("assets", exist_ok=True)

    while True:
        try:
            logging.info(f"[SCHED] Refreshing prayer times ({city}, {country})")
            times = get_prayer_times(city, country, method)

            if times:
                with open("assets/prayer_times.json", "w", encoding="utf-8") as f:
                    json.dump(
                        {k: str(v) for k, v in times.items()},
                        f,
                        indent=2,
                    )
                logging.info("[SCHED] Prayer times updated")
            else:
                logging.warning("[SCHED] Prayer API returned no data")

        except Exception:
            logging.error("[SCHED] Prayer refresh failed", exc_info=True)

        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        time.sleep((next_midnight - now).total_seconds())



def main():
    setup_logging()
    logging.info("[CORE] AdhaanLive started")

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
