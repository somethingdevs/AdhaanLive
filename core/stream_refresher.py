import time
import base64
import json
import urllib.parse
import logging
from typing import Callable, Optional
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "..", "assets", "current_stream.txt")
CACHE_PATH = os.path.normpath(CACHE_PATH)


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


def read_cached_url() -> Optional[str]:
    """Reads the cached stream URL if it exists."""
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r") as f:
            url = f.read().strip()
            return url if url else None
    except Exception:
        return None


def smart_refresh_loop(get_new_url_func: Callable[[], str]) -> None:
    """
    Refreshes the livestream URL only when needed.
    - Checks cache on startup.
    - Reuses valid URL until expiry.
    - Refreshes 2 minutes before expiry.
    """
    logging.info("🚀 Starting Smart Stream Refresher...")

    while True:
        try:
            url = read_cached_url()

            if url:
                exp = decode_expiry_from_token(url)
                now = int(time.time())
                if exp and exp > now + 180:  # still valid for at least 3 minutes
                    expiry_time = time.strftime("%H:%M:%S", time.localtime(exp))
                    logging.info(f"✅ Using cached stream URL (valid until {expiry_time})")
                    sleep_for = max(0, (exp - now) - 120)
                    logging.info(f"💤 Sleeping {sleep_for / 60:.1f} min before next refresh.")
                    time.sleep(sleep_for)
                    logging.info("🔄 Refreshing token soon...")
                else:
                    logging.info("⚠️ Cached token expired or invalid. Fetching new URL...")
                    url = get_new_url_func()
            else:
                logging.info("📂 No cached stream URL found. Fetching new one...")
                url = get_new_url_func()

            if not url:
                logging.warning("⚠️ Could not retrieve a new stream URL. Retrying in 10 minutes...")
                time.sleep(600)
                continue

            # 💾 Save the fresh URL
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, "w") as f:
                f.write(url)
            logging.info(f"💾 Saved new stream URL to {CACHE_PATH}")

            # 🧠 Decode expiry and sleep
            exp = decode_expiry_from_token(url)
            if not exp:
                logging.warning("⚠️ Couldn’t decode expiry; defaulting to 2 hours.")
                time.sleep(7200)
                continue

            now = int(time.time())
            sleep_for = max(0, (exp - now) - 120)
            expiry_time = time.strftime("%H:%M:%S", time.localtime(exp))
            logging.info(f"🕒 Token valid until {expiry_time} — sleeping for {sleep_for / 60:.1f} min")

            time.sleep(sleep_for)
            logging.info("🔄 Token expiring soon, refreshing now...")

        except KeyboardInterrupt:
            logging.info("🛑 Stream refresher stopped manually.")
            break
        except Exception as e:
            logging.exception(f"❌ Unexpected error in stream refresher: {e}")
            logging.info("Retrying in 5 minutes...")
            time.sleep(300)
