# =====================================
# stream_refresher.py — STATE-CENTRALIZED
# =====================================

import time
import threading
import logging
from typing import Callable, Optional

from core.runtime_state import state

# -------------------------------------
# CONFIG
# -------------------------------------

REFRESH_INTERVAL_SEC = 15 * 60        # refresh every 15 min
RETRY_INTERVAL_SEC = 30               # retry on failure
LOCKOUT_CHECK_SEC = 10                # how often we re-check state


# -------------------------------------
# StreamRefresher
# -------------------------------------

class StreamRefresher:
    """
    Periodically refreshes the stream URL.
    Respects runtime_state to avoid disrupting
    detection or playback.
    """

    def __init__(self, fetch_stream_url_fn: Callable[[], Optional[str]]):
        self.fetch_stream_url_fn = fetch_stream_url_fn

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._current_url: Optional[str] = None
        self._last_refresh_ts: float = 0.0

    # -----------------------------
    # Public API
    # -----------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="StreamRefresher",
            daemon=True,
        )
        self._thread.start()

        logging.info("[STREAM] Refresher started")

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._thread = None
        logging.info("[STREAM] Refresher stopped")

    def get_stream_url(self) -> Optional[str]:
        with self._lock:
            return self._current_url

    # -----------------------------
    # Internals
    # -----------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                # ---------------------------------
                # Respect active system state
                # ---------------------------------
                if state.adhaan_active or state.playback_active:
                    logging.debug(
                        "[STREAM] Adhaan/playback active — deferring refresh"
                    )
                    time.sleep(LOCKOUT_CHECK_SEC)
                    continue

                # ---------------------------------
                # Refresh window
                # ---------------------------------
                now = time.time()
                if now - self._last_refresh_ts < REFRESH_INTERVAL_SEC:
                    time.sleep(5)
                    continue

                logging.info("[STREAM] Refreshing stream URL")
                new_url = self.fetch_stream_url_fn()

                if not new_url:
                    logging.warning("[STREAM] Failed to fetch stream URL")
                    time.sleep(RETRY_INTERVAL_SEC)
                    continue

                with self._lock:
                    if new_url != self._current_url:
                        self._current_url = new_url
                        logging.info("[STREAM] Stream URL updated")

                self._last_refresh_ts = now

            except Exception:
                logging.error("[STREAM] Refresher error", exc_info=True)
                time.sleep(RETRY_INTERVAL_SEC)


def get_current_stream_url() -> Optional[str]:
    if STREAM_REFRESHER:
        return STREAM_REFRESHER.get_stream_url()
    return None

# -------------------------------------
# Convenience singleton
# -------------------------------------

STREAM_REFRESHER: Optional[StreamRefresher] = None


def start_stream_refresher(fetch_stream_url_fn: Callable[[], Optional[str]]):
    global STREAM_REFRESHER

    if STREAM_REFRESHER is None:
        STREAM_REFRESHER = StreamRefresher(fetch_stream_url_fn)

    STREAM_REFRESHER.start()
    return STREAM_REFRESHER
