import threading
import logging
import time
import os
from typing import Optional

# === Imports ===
from core.stream_refresher import smart_refresh_loop, CACHE_PATH
from utils.livestream import get_new_url_func

from core.detector import (
    start_audio_detection,
    stop_audio_detection,
    start_ambient_monitor,
    stop_ambient_monitor,
)
from core.playback import (
    start_buffered_playback,
    stop_buffered_playback,
)

# Optional: if your detector exposes a getter for the latest ambient stats
try:
    from core.detector import get_ambient_snapshot  # returns dict or None
except Exception:  # keep running even if not present
    get_ambient_snapshot = None

# === Logging setup ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# === Global control & status flags ===
stop_flag = threading.Event()
detection_active_flag = threading.Event()
ambient_active_flag = threading.Event()
playback_active_flag = threading.Event()


def _read_cached_url() -> str:
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _volume_bar(db: Optional[float], width: int = 12) -> str:
    """
    Tiny ASCII volume meter based on dB (0 dB = full, -60 dB = empty).
    If db is None, returns blanks.
    """
    if db is None:
        return "[" + (" " * width) + "]"
    # clamp to [-60, 0] dB
    db = max(min(db, 0.0), -60.0)
    # map to 0..width
    filled = int(round((db + 60.0) / 60.0 * width))
    return "[" + ("#" * filled) + (" " * (width - filled)) + "]"


def heartbeat_status(poll_interval: int = 60):
    """
    Periodically logs system health + visual volume meter.
    Includes live ▲▼ trend indicators from ambient snapshot.
    """
    last_db = None

    while not stop_flag.is_set():
        try:
            url = _read_cached_url()
            url_short = (url[:90] + "…") if len(url) > 100 else url
            last_mtime = os.path.getmtime(CACHE_PATH) if os.path.exists(CACHE_PATH) else None
            last_mtime_str = time.strftime("%H:%M:%S", time.localtime(last_mtime)) if last_mtime else "N/A"

            db, peak, trend_symbol = None, None, "·"

            if callable(get_ambient_snapshot):
                snap = get_ambient_snapshot()
                if snap:
                    db = snap.get("db")
                    peak = snap.get("peak")

                    # simple trend calc vs last db
                    if last_db is not None and db is not None:
                        if db > last_db + 0.5:
                            trend_symbol = "▲"
                        elif db < last_db - 0.5:
                            trend_symbol = "▼"
                    last_db = db

            # tiny visual bar
            bar = _volume_bar(db)
            db_str = f"{db:.1f} dB" if db is not None else "N/A"
            peak_str = f"{peak:.3f}" if peak is not None else "N/A"

            logging.info(
                "💓 Heartbeat | detect=%s | ambient=%s | playback=%s | %s %s | peak=%s | cache=%s | url=%s",
                detection_active_flag.is_set(),
                ambient_active_flag.is_set(),
                playback_active_flag.is_set(),
                bar,
                trend_symbol + " " + db_str,
                peak_str,
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
    ambient monitor + detection + playback when a new stream URL is written.
    """
    logging.info("👁️  Starting stream watcher...")

    last_mtime = None
    last_url = None

    # 🆕 Auto-start pipeline if a valid cached URL exists
    cached_url = _read_cached_url()
    if cached_url:
        try:
            logging.info("🚀 Auto-starting ambient + detection + playback with cached URL...")
            # Start in safe order: ambient → detection → playback
            start_ambient_monitor(cached_url)
            ambient_active_flag.set()

            time.sleep(0.5)  # tiny spacing to avoid FFmpeg races

            start_audio_detection(cached_url)
            detection_active_flag.set()

            time.sleep(0.5)

            start_buffered_playback(cached_url)
            playback_active_flag.set()

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
                        logging.info("🔄 Stream URL changed — restarting ambient + detection + playback...")

                        # Stop in safe order: detection → playback → ambient
                        try:
                            stop_audio_detection()
                        finally:
                            detection_active_flag.clear()

                        try:
                            stop_buffered_playback()
                        finally:
                            playback_active_flag.clear()

                        try:
                            stop_ambient_monitor()
                        finally:
                            ambient_active_flag.clear()

                        time.sleep(1.0)  # spacing to ensure old FFmpeg is fully down

                        # Start in safe order: ambient → detection → playback
                        start_ambient_monitor(new_url)
                        ambient_active_flag.set()

                        time.sleep(0.5)

                        start_audio_detection(new_url)
                        detection_active_flag.set()

                        time.sleep(0.5)

                        start_buffered_playback(new_url)
                        playback_active_flag.set()

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

    # Start watcher thread (triggers ambient + detection + playback)
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

        # Stop pipeline in safe order: detection → playback → ambient
        try:
            stop_audio_detection()
        finally:
            detection_active_flag.clear()

        try:
            stop_buffered_playback()
        finally:
            playback_active_flag.clear()

        try:
            stop_ambient_monitor()
        finally:
            ambient_active_flag.clear()

        # Join threads
        refresher_thread.join(timeout=3)
        watcher_thread.join(timeout=3)
        heartbeat_thread.join(timeout=3)

        logging.info("✅ All threads stopped cleanly.")


if __name__ == "__main__":
    main()
