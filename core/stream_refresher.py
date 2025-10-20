import base64
import json
import time
import logging
import os
import urllib
from datetime import datetime, timedelta
from typing import Optional

from utils.livestream import get_new_url_func
from core.detector import is_adhaan_active  # requires mark_adhaan_active() in detector

CACHE_PATH = os.path.join("assets", "current_stream.txt")


def decode_expiry_from_token(token_url: str) -> Optional[int]:
    """Extracts and decodes the JWT token from the .m3u8 URL to get expiry (epoch seconds)."""
    try:
        token = urllib.parse.unquote(token_url.split("token=")[1])
        payload_b64 = token.split(".")[1]
        payload_json = base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8")
        payload = json.loads(payload_json)
        return payload.get("exp", 0)
    except Exception as e:
        logging.warning(f"⚠️ Failed to decode token expiry: {e}")
        return None


def _read_cached_url():
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _write_cached_url(url: str):
    """Safely writes the new stream URL to cache file."""
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            f.write(url)
        logging.info(f"💾 Saved new stream URL to {CACHE_PATH}")
    except Exception as e:
        logging.error(f"❌ Failed to write new stream URL: {e}")


def smart_refresh_loop(get_new_url_func):
    """
    Smart refresher that prefetches Angelcam URLs early (10 min before expiry)
    but defers activating them if Adhaan is in progress.
    """

    PREFETCH_WINDOW = 600  # 10 min before expiry
    SWAP_CUTOFF = 30  # Force swap 30s before expiry
    REFRESH_INTERVAL = 60  # Main loop sleep

    logging.info("🚀 Starting Smart Stream Refresher...")

    cached_url = _read_cached_url()
    expiry_time = None
    next_url = None
    prefetch_done = False

    # 🩵 NEW: ensure we start with a valid URL if none exists
    if not cached_url:
        logging.info("🌐 No cached stream URL found — fetching initial one...")
        try:
            new_url = get_new_url_func()
            if isinstance(new_url, tuple):
                new_url = new_url[0]
            _write_cached_url(new_url)
            cached_url = new_url
            expiry_time = datetime.utcnow() + timedelta(hours=2)
            logging.info("✅ Initial stream URL fetched and cached successfully.")
        except Exception as e:
            logging.error(f"❌ Failed to fetch initial stream URL: {e}")
            time.sleep(30)  # retry soon
            return smart_refresh_loop(get_new_url_func)

    while True:
        try:
            now = datetime.utcnow()

            # Fallback: assume 2h token validity if unknown
            if not expiry_time:
                expiry_time = now + timedelta(hours=2)

            time_left = (expiry_time - now).total_seconds()

            # --- Step 1: Prefetch Early ---
            if time_left < PREFETCH_WINDOW and not prefetch_done:
                logging.info("🕐 Prefetching new stream URL early (token near expiry)...")
                try:
                    next_url = get_new_url_func()
                    prefetch_done = True
                    logging.info("✅ Prefetched next URL successfully (holding until safe swap).")
                except Exception as e:
                    logging.warning(f"⚠️ Failed to prefetch new URL early: {e}")

            # --- Step 2: Swap Logic ---
            if prefetch_done and next_url:
                if not is_adhaan_active():
                    logging.info("🔄 Activating prefetched URL (Adhaan idle)...")
                    _write_cached_url(next_url)
                    cached_url = next_url
                    expiry_time = now + timedelta(hours=2)
                    prefetch_done = False
                    next_url = None
                elif time_left < SWAP_CUTOFF:
                    logging.warning("⏳ Token near expiry but Adhaan active — forcing swap to avoid drop.")
                    _write_cached_url(next_url)
                    cached_url = next_url
                    expiry_time = now + timedelta(hours=2)
                    prefetch_done = False
                    next_url = None
                else:
                    logging.info("🕊️ Holding prefetched URL — Adhaan still active.")

            # --- Step 3: Emergency Refresh ---
            elif time_left <= 0:
                logging.warning("⚠️ Token expired unexpectedly — fetching new URL now.")
                try:
                    new_url = get_new_url_func()
                    _write_cached_url(new_url)
                    cached_url = new_url
                    expiry_time = now + timedelta(hours=2)
                except Exception as e:
                    logging.error(f"❌ Failed to refresh URL after expiry: {e}")

            time.sleep(REFRESH_INTERVAL)

        except Exception as e:
            logging.exception(f"❌ Smart refresher crashed: {e}")
            time.sleep(30)
