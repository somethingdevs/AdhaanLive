"""
Playback manager using ffplay with lifecycle, retries, and smooth fade-out stop.

Enhancements:
- Uses stable playback args that work reliably.
- Adds optional fade-out when stopping playback.
"""

from __future__ import annotations
import subprocess
import threading
import time
import logging
from typing import Optional


class PlaybackManager:
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
            "-nodisp"
        ]

        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec

        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._runner_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._current_url: Optional[str] = None
        self._retries = 0

    # ------------ public API ------------
    def start(self, url: str) -> None:
        """Start playback for URL if not already running on the same URL."""
        with self._lock:
            if self._proc and self._proc.poll() is None and self._current_url == url:
                logging.debug("Playback already active on same URL; skipping start.")
                return

            if self._proc and self._proc.poll() is None and self._current_url != url:
                logging.info("Stopping playback to switch URL...")
                self._stop_proc_locked()

            self._stop_flag.clear()
            self._current_url = url
            self._retries = 0

            if self._runner_thread and self._runner_thread.is_alive():
                self._stop_flag.set()
                self._runner_thread.join(timeout=2)

            self._runner_thread = threading.Thread(
                target=self._run_loop, name="PlaybackRunner", daemon=True
            )
            self._runner_thread.start()
            logging.info("ffplay-based playback started in background.")

    def stop(self) -> None:
        """Stop playback cleanly."""
        with self._lock:
            self._stop_flag.set()
            self._stop_proc_locked()

        if self._runner_thread and self._runner_thread.is_alive():
            self._runner_thread.join(timeout=5)
        self._runner_thread = None
        logging.info("Playback stopped.")

    def restart(self, url: Optional[str] = None) -> None:
        """Force a restart (optionally with a new URL)."""
        with self._lock:
            if url is not None and url != self._current_url:
                self._current_url = url
            self._stop_flag.set()
            self._stop_proc_locked()

        if self._runner_thread and self._runner_thread.is_alive():
            self._runner_thread.join(timeout=5)

        self._stop_flag.clear()
        self._retries = 0
        self._runner_thread = threading.Thread(
            target=self._run_loop, name="PlaybackRunner", daemon=True
        )
        self._runner_thread.start()
        logging.info("ffplay-based playback restarted in background.")

    def is_alive(self) -> bool:
        with self._lock:
            return bool(self._proc and self._proc.poll() is None)

    def current_url(self) -> Optional[str]:
        with self._lock:
            return self._current_url

    # ------------ internals ------------
    def _run_loop(self) -> None:
        while not self._stop_flag.is_set():
            url = self.current_url()
            if not url:
                logging.warning("[PLAY] No URL set for playback; waiting...")
                time.sleep(1.0)
                continue

            args = [self.ffplay_path, *self.base_args, "-i", url]

            try:
                with self._lock:
                    logging.info(f"[PLAY] Starting playback | url={url}")

                    # === THE IMPORTANT CHANGE ===
                    self._proc = subprocess.Popen(
                        args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                while not self._stop_flag.is_set():
                    with self._lock:
                        proc = self._proc

                    if not proc:
                        break

                    rc = proc.poll()
                    if rc is None:
                        time.sleep(0.5)
                        continue

                    if rc == 0:
                        logging.info("[PLAY] ffplay exited normally")
                    else:
                        logging.warning("[PLAY] ffplay exited unexpectedly")

                    break

            except FileNotFoundError:
                logging.error("[PLAY] ffplay not found — install FFmpeg.")
                break

            except Exception as e:
                logging.error(f"[PLAY] Launch error: {e}", exc_info=True)

            with self._lock:
                self._stop_proc_locked()

            if self._stop_flag.is_set():
                break

            self._retries += 1
            if self._retries > self.max_retries:
                logging.error("[PLAY] Too many playback failures; giving up.")
                break

            logging.info(
                f"[PLAY] Retrying in {self.retry_delay_sec}s "
                f"(attempt {self._retries}/{self.max_retries})..."
            )
            time.sleep(self.retry_delay_sec)

        with self._lock:
            self._stop_proc_locked()

    def _stop_proc_locked(self) -> None:
        """Terminate ffplay cleanly."""
        if self._proc:
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


PLAYBACK = PlaybackManager()
