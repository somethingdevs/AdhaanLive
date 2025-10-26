import threading
import logging
import time
import os

from core.stream_refresher import smart_refresh_loop, CACHE_PATH
from utils.livestream import get_new_url_func

# Detection + ambient monitor (with snapshot support)
from core.detector import (
    start_audio_detection,
    stop_audio_detection,
    start_ambient_monitor,
    stop_ambient_monitor,
)

from core.playback import PLAYBACK

try:
    from core.detector import get_ambient_snapshot  # returns dict
except Exception:
    get_ambient_snapshot = None

# === Logging setup ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# === Global control & flags ===
stop_flag = threading.Event()
detection_active_flag = threading.Event()
ambient_active_flag = threading.Event()
watchdog_status = {"last_restart": None, "last_action": "OK"}


def _read_cached_url() -> str:
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _volume_bar(db: float or None, width: int = 12) -> str:
    """Tiny ASCII bar based on dB."""
    if db is None:
        return "[" + (" " * width) + "]"
    db = max(min(db, 0.0), -60.0)
    filled = int(round((db + 60.0) / 60.0 * width))
    return "[" + ("#" * filled) + (" " * (width - filled)) + "]"


def heartbeat_status(poll_interval: int = 60):
    """Periodic system heartbeat with volume and watchdog state."""
    last_db = None

    while not stop_flag.is_set():
        try:
            url = _read_cached_url()
            url_short = (url[:90] + "…") if len(url) > 100 else url
            mtime = os.path.getmtime(CACHE_PATH) if os.path.exists(CACHE_PATH) else None
            mtime_str = time.strftime("%H:%M:%S", time.localtime(mtime)) if mtime else "N/A"

            db, peak, trend_symbol = None, None, "·"
            if callable(get_ambient_snapshot):
                snap = get_ambient_snapshot()
                if snap:
                    db = snap.get("db")
                    peak = snap.get("peak")
                    if last_db is not None and db is not None:
                        if db > last_db + 0.5:
                            trend_symbol = "▲"
                        elif db < last_db - 0.5:
                            trend_symbol = "▼"
                    last_db = db

            bar = _volume_bar(db)
            db_str = f"{db:.1f} dB" if db is not None else "N/A"
            peak_str = f"{peak:.3f}" if peak is not None else "N/A"
            wd_str = (
                f"{watchdog_status['last_action']} @ {watchdog_status['last_restart']}"
                if watchdog_status["last_restart"] else "OK"
            )

            logging.info(
                "💓 Heartbeat | detect=%s | ambient=%s | wd=%s | %s %s | peak=%s | cache=%s | url=%s",
                detection_active_flag.is_set(),
                ambient_active_flag.is_set(),
                wd_str,
                bar,
                trend_symbol + " " + db_str,
                peak_str,
                mtime_str,
                url_short if url_short else "N/A",
            )

        except Exception as e:
            logging.debug(f"Heartbeat error (non-fatal): {e}")
        finally:
            time.sleep(poll_interval)


def monitor_stream_updates(poll_interval: int = 5):
    """Watches cache file and restarts ambient + detection when stream URL changes."""
    logging.info("👁️  Starting stream watcher...")
    last_mtime, last_url = None, None

    cached_url = _read_cached_url()
    if cached_url:
        try:
            logging.info("🚀 Auto-starting ambient + detection with cached URL...")
            start_ambient_monitor(cached_url)
            ambient_active_flag.set()
            time.sleep(0.5)
            start_audio_detection(cached_url)
            detection_active_flag.set()
            last_url = cached_url
            last_mtime = os.path.getmtime(CACHE_PATH)
        except Exception as e:
            logging.warning(f"⚠️ Could not auto-start from cache: {e}")

    while not stop_flag.is_set():
        try:
            if os.path.exists(CACHE_PATH):
                mtime = os.path.getmtime(CACHE_PATH)
                if last_mtime is None or mtime != last_mtime:
                    with open(CACHE_PATH, "r") as f:
                        new_url = f.read().strip()
                    if new_url and new_url != last_url:
                        logging.info("🔄 Stream URL changed — restarting ambient + detection...")

                        stop_audio_detection()
                        detection_active_flag.clear()
                        stop_ambient_monitor()
                        ambient_active_flag.clear()
                        PLAYBACK.stop()  # ✅ ensure playback killed safely
                        time.sleep(1.0)

                        start_ambient_monitor(new_url)
                        ambient_active_flag.set()
                        time.sleep(0.5)
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


def watchdog_monitor(poll_interval: int = 30):
    """Smart watchdog that checks thread health and restarts if idle."""
    logging.info("🧩 Smart Watchdog started.")
    while not stop_flag.is_set():
        try:
            url = _read_cached_url()
            if not url:
                time.sleep(poll_interval)
                continue

            # --- Ambient monitor check ---
            try:
                snap = get_ambient_snapshot() if callable(get_ambient_snapshot) else None
                last_update_age = (time.time() - snap["timestamp"]) if snap and snap.get("timestamp") else None
            except Exception:
                last_update_age = None

            if not ambient_active_flag.is_set() or (last_update_age and last_update_age > 45):
                logging.warning("⚠️ Watchdog: Ambient monitor inactive/stale, restarting...")
                try:
                    stop_ambient_monitor()
                    start_ambient_monitor(url)
                    ambient_active_flag.set()
                    watchdog_status.update(
                        {"last_restart": time.strftime("%H:%M:%S"), "last_action": "Ambient Restart"}
                    )
                    logging.info("🧩 Watchdog: Ambient monitor restarted.")
                except Exception as e:
                    logging.error(f"❌ Watchdog failed to restart ambient: {e}")

            # --- Detection thread check ---
            from core.detector import _detection_in_progress
            if not detection_active_flag.is_set():
                if _detection_in_progress.is_set():
                    logging.info("🧠 Watchdog: Detection already in progress — skipping restart.")
                else:
                    logging.warning("⚠️ Watchdog: Detection idle, restarting...")
                    try:
                        start_audio_detection(url)
                        detection_active_flag.set()
                        watchdog_status.update(
                            {"last_restart": time.strftime("%H:%M:%S"), "last_action": "Detection Restart"}
                        )
                        logging.info("🧩 Watchdog: Detection restarted.")
                    except Exception as e:
                        logging.error(f"❌ Watchdog failed to restart detection: {e}")

        except Exception as e:
            logging.exception(f"❌ Watchdog general error: {e}")
        finally:
            time.sleep(poll_interval)


def run_stream_refresher():
    """Background thread for dynamic URL refresh."""
    try:
        smart_refresh_loop(get_new_url_func)
    except Exception as e:
        logging.exception(f"❌ Stream refresher crashed: {e}")


def main():
    logging.info("🚀 Starting Adhaan Live System...")

    refresher_thread = threading.Thread(target=run_stream_refresher, daemon=True)
    refresher_thread.start()

    watcher_thread = threading.Thread(target=monitor_stream_updates, daemon=True)
    watcher_thread.start()

    heartbeat_thread = threading.Thread(target=heartbeat_status, daemon=True)
    heartbeat_thread.start()

    watchdog_thread = threading.Thread(target=watchdog_monitor, daemon=True)
    watchdog_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("🛑 Shutting down gracefully...")
        stop_flag.set()

        stop_audio_detection()
        detection_active_flag.clear()
        stop_ambient_monitor()
        ambient_active_flag.clear()
        PLAYBACK.stop()

        refresher_thread.join(timeout=3)
        watcher_thread.join(timeout=3)
        heartbeat_thread.join(timeout=3)
        watchdog_thread.join(timeout=3)
        logging.info("✅ All threads stopped cleanly.")


if __name__ == "__main__":
    main()
