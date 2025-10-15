import threading
import logging
import time
import os

# === Imports ===
from core.stream_refresher import smart_refresh_loop, CACHE_PATH
from utils.livestream import get_new_url_func
from core.detector import (
    start_audio_detection,
    stop_audio_detection,
    start_ambient_monitor,
    stop_ambient_monitor,
)

# === Logging setup ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# === Global control & status flags ===
stop_flag = threading.Event()
detection_active_flag = threading.Event()
ambient_active_flag = threading.Event()


def _read_cached_url() -> str:
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def heartbeat_status(poll_interval: int = 60):
    """
    Periodically logs system health so you can see at a glance what's up.
    """
    while not stop_flag.is_set():
        try:
            url = _read_cached_url()
            url_short = (url[:90] + "…") if len(url) > 100 else url
            last_mtime = os.path.getmtime(CACHE_PATH) if os.path.exists(CACHE_PATH) else None
            last_mtime_str = time.strftime("%H:%M:%S", time.localtime(last_mtime)) if last_mtime else "N/A"

            logging.info(
                "💓 Heartbeat | detection_active=%s | ambient_active=%s | cache_mtime=%s | url=%s",
                detection_active_flag.is_set(),
                ambient_active_flag.is_set(),
                last_mtime_str,
                url_short if url_short else "N/A",
            )
        except Exception as e:
            logging.debug(f"Heartbeat error (non-fatal): {e}")
        finally:
            time.sleep(poll_interval)


def monitor_stream_updates(poll_interval: int = 5):
    """
    Watches the current_stream.txt file for changes and triggers
    audio + ambient detection when a new stream URL is written.
    """
    logging.info("👁️  Starting stream watcher...")

    last_mtime = None
    last_url = None

    # 🆕 Auto-start detection if a valid cached URL exists
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r") as f:
                cached_url = f.read().strip()
            if cached_url:
                logging.info("🚀 Auto-starting detection and ambient monitor with cached URL...")
                start_ambient_monitor(cached_url)
                start_audio_detection(cached_url)
                ambient_active_flag.set()
                detection_active_flag.set()
                last_url = cached_url
                last_mtime = os.path.getmtime(CACHE_PATH)
        except Exception as e:
            logging.warning(f"⚠️ Could not auto-start from cache: {e}")

    # 🌀 Continuous watcher loop
    while not stop_flag.is_set():
        try:
            if os.path.exists(CACHE_PATH):
                mtime = os.path.getmtime(CACHE_PATH)
                if last_mtime is None or mtime != last_mtime:
                    with open(CACHE_PATH, "r") as f:
                        new_url = f.read().strip()

                    if new_url and new_url != last_url:
                        logging.info("🔄 Stream URL changed — restarting ambient + detection threads...")
                        # Stop current
                        stop_audio_detection()
                        detection_active_flag.clear()
                        stop_ambient_monitor()
                        ambient_active_flag.clear()

                        time.sleep(1)  # small delay to avoid race with FFmpeg

                        # Start new
                        start_ambient_monitor(new_url)
                        ambient_active_flag.set()
                        start_audio_detection(new_url)
                        detection_active_flag.set()

                        last_url = new_url

                    last_mtime = mtime

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            logging.info("🛑 Stream watcher stopped manually.")
            break
        except Exception as e:
            logging.exception(f"❌ Error in stream watcher: {e}")
            time.sleep(5)


def run_stream_refresher():
    """Background thread for dynamic URL refresh."""
    try:
        smart_refresh_loop(get_new_url_func)
    except Exception as e:
        logging.exception(f"❌ Stream refresher crashed: {e}")


def main():
    logging.info("🚀 Starting Adhaan Live System...")

    # Start refresher thread (updates stream URL periodically)
    refresher_thread = threading.Thread(target=run_stream_refresher, daemon=True)
    refresher_thread.start()

    # Start watcher thread (triggers detection + ambient monitor)
    watcher_thread = threading.Thread(target=monitor_stream_updates, daemon=True)
    watcher_thread.start()

    # Start heartbeat thread (status every minute)
    heartbeat_thread = threading.Thread(target=heartbeat_status, daemon=True)
    heartbeat_thread.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("🛑 Shutting down gracefully...")
        stop_flag.set()

        # Stop detection & ambient
        try:
            stop_audio_detection()
            detection_active_flag.clear()
        except Exception:
            pass
        try:
            stop_ambient_monitor()
            ambient_active_flag.clear()
        except Exception:
            pass

        # Join threads
        refresher_thread.join(timeout=3)
        watcher_thread.join(timeout=3)
        heartbeat_thread.join(timeout=3)

        logging.info("✅ All threads stopped cleanly.")


if __name__ == "__main__":
    main()
