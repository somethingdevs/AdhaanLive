# --- CLEAN LOGGING VERSION OF stream_refresher.py ---

import base64
import json
import time
import logging
import os
import urllib
from datetime import datetime, timedelta
from typing import Optional

from utils.livestream import get_new_url_func
from core.detector import is_adhaan_active   # used only to delay token swap

CACHE_PATH = os.path.join("assets", "current_stream.txt")


# ------------------------------------------------------
# Token expiry decoding
# ------------------------------------------------------
def decode_expiry_from_token(token_url: str) -> Optional[int]:
    """Extract `exp` from the Angelcam JWT inside the m3u8 URL."""
    try:
        token = urllib.parse.unquote(token_url.split("token=")[1])
        payload_b64 = token.split(".")[1]
        payload_json = base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8")
        payload = json.loads(payload_json)
        return payload.get("exp", 0)
    except Exception as e:
        logging.warning(f"[REFRESH] Unable to decode token expiry: {e}")
        return None


# ------------------------------------------------------
# Cache helpers
# ------------------------------------------------------
def _read_cached_url():
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _write_cached_url(url: str):
    """Persist HLS URL to disk."""
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            f.write(url)
        logging.info(f"[REFRESH] Updated cached stream URL")
    except Exception as e:
        logging.error(f"[REFRESH] Failed to write stream URL: {e}")


# ------------------------------------------------------
# Main refresher loop
# ------------------------------------------------------
def smart_refresh_loop(get_new_url_func):
    """
    Manages Angelcam m3u8 URL renewal.
    Prefetch early, activate safely when Adhaan is idle.
    """

    PREFETCH_WINDOW = 600   # 10 minutes
    SWAP_CUTOFF = 30        # force swap 30 seconds before expiry
    REFRESH_INTERVAL = 60   # main loop sleep

    logging.info("[REFRESH] Stream refresher started")

    cached_url = _read_cached_url()
    expiry_time = None
    next_url = None
    prefetch_done = False

    # If no stream URL exists yet → fetch immediately
    if not cached_url:
        logging.info("[REFRESH] No cached URL — fetching initial stream")
        try:
            new_url = get_new_url_func()
            if isinstance(new_url, tuple):
                new_url = new_url[0]

            _write_cached_url(new_url)
            cached_url = new_url
            expiry_time = datetime.utcnow() + timedelta(hours=2)
            logging.info("[REFRESH] Initial URL fetched")
        except Exception as e:
            logging.error(f"[REFRESH] Failed to fetch initial URL: {e}")
            time.sleep(30)
            return smart_refresh_loop(get_new_url_func)

    # --------------------------------------------------
    # Continuous refresh loop
    # --------------------------------------------------
    while True:
        try:
            now = datetime.utcnow()

            # If no expiry known, assume 2 hours validity
            if not expiry_time:
                expiry_time = now + timedelta(hours=2)

            time_left = (expiry_time - now).total_seconds()

            # ------------------------------------------
            # Prefetch new URL early
            # ------------------------------------------
            if time_left < PREFETCH_WINDOW and not prefetch_done:
                logging.info("[REFRESH] Prefetching new token")
                try:
                    next_url = get_new_url_func()
                    prefetch_done = True
                    logging.info("[REFRESH] Prefetch complete")
                except Exception as e:
                    logging.warning(f"[REFRESH] Prefetch failed: {e}")

            # ------------------------------------------
            # Safe Swap Logic
            # ------------------------------------------
            if prefetch_done and next_url:
                adhaan_active = is_adhaan_active()

                # Swap immediately if safe
                if not adhaan_active:
                    logging.info("[REFRESH] Activating new token (idle)")
                    _write_cached_url(next_url)
                    cached_url = next_url
                    expiry_time = now + timedelta(hours=2)
                    next_url = None
                    prefetch_done = False

                # Forced swap if token is about to expire
                elif time_left < SWAP_CUTOFF:
                    logging.warning("[REFRESH] Forced token swap (near expiry)")
                    _write_cached_url(next_url)
                    cached_url = next_url
                    expiry_time = now + timedelta(hours=2)
                    next_url = None
                    prefetch_done = False

            # ------------------------------------------
            # Emergency refresh if expired
            # ------------------------------------------
            elif time_left <= 0:
                logging.warning("[REFRESH] Token expired — fetching new URL")
                try:
                    new_url = get_new_url_func()
                    _write_cached_url(new_url)
                    cached_url = new_url
                    expiry_time = now + timedelta(hours=2)
                except Exception as e:
                    logging.error(f"[REFRESH] Emergency refresh failed: {e}")

            time.sleep(REFRESH_INTERVAL)

        except Exception as e:
            logging.error(f"[REFRESH] Refresher crashed: {e}")
            time.sleep(30)
