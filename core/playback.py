from __future__ import annotations

import subprocess
import threading
import time
import logging
from typing import Optional

from core.runtime_state import state


class PlaybackManager:
    """
    Executes audio playback using ffplay.
    Owns its own thread and process.
    Publishes playback status ONLY via runtime_state.
    """

    def __init__(
        self,
        ffplay_path: str = "ffplay",
        base_args: Optional[list[str]] = None,
        max_retries: int = 3,
        retry_delay_sec: float = 5.0,
    ):
        self.ffplay_path = ffplay_path
        self.base_args = base_args or [
            "-loglevel", "error",
            "-autoexit",
            "-vn",
            "-nodisp",
        ]

        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._proc: Optional[subprocess.Popen] = None
        self._url: Optional[str] = None
        self._retries = 0

    # -----------------------------
    # PUBLIC API
    # -----------------------------

    def start(self, url: str) -> None:
        """Start playback for a given URL."""
        with self._lock:
            if state.playback_active and self._url == url:
                logging.debug("[PLAY] Playback already active on same URL")
                return

            self.stop()

            self._url = url
            self._stop_event.clear()
            self._retries = 0

            self._thread = threading.Thread(
                target=self._run_loop,
                name="PlaybackThread",
                daemon=True,
            )
            self._thread.start()

            logging.info(f"[PLAY] Playback requested | url={url}")

    def stop(self) -> None:
        """Stop playback immediately."""
        with self._lock:
            self._stop_event.set()
            self._terminate_proc_locked()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._thread = None
        self._url = None

        state.stop_playback()
        logging.info("[PLAY] Playback stopped")

    def is_running(self) -> bool:
        return state.playback_active

    # -----------------------------
    # INTERNALS
    # -----------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():

            if not self._url:
                time.sleep(0.5)
                continue

            cmd = [
                self.ffplay_path,
                *self.base_args,
                "-i",
                self._url,
            ]

            try:
                logging.info(f"[PLAY] Launching ffplay | url={self._url}")

                with self._lock:
                    self._proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    state.start_playback()

                while not self._stop_event.is_set():
                    if self._proc.poll() is not None:
                        break
                    time.sleep(0.5)

                logging.info("[PLAY] ffplay exited")

            except FileNotFoundError:
                logging.error("[PLAY] ffplay not found (FFmpeg missing)")
                break

            except Exception as e:
                logging.error(f"[PLAY] Playback error: {e}", exc_info=True)

            finally:
                with self._lock:
                    self._terminate_proc_locked()
                    state.stop_playback()

            if self._stop_event.is_set():
                break

            self._retries += 1
            if self._retries > self.max_retries:
                logging.error("[PLAY] Max retries exceeded; aborting playback")
                break

            logging.info(
                f"[PLAY] Retrying playback in {self.retry_delay_sec}s "
                f"({self._retries}/{self.max_retries})"
            )
            time.sleep(self.retry_delay_sec)

    def _terminate_proc_locked(self) -> None:
        if not self._proc:
            return

        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        except Exception:
            pass
        finally:
            self._proc = None


# Singleton used by detector / API
PLAYBACK = PlaybackManager()
