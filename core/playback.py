"""
Playback manager using ffplay with sane lifecycle + retries.

- Starts ffplay as a subprocess
- Tracks process health and current URL
- Retries on crash (max_retries, retry_delay)
- Only restarts when the URL actually changes or the process dies
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
        self.base_args = base_args or ["-nodisp", "-autoexit", "-loglevel", "error"]
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
            # If running on same URL, keep it
            if self._proc and self._proc.poll() is None and self._current_url == url:
                logging.debug("Playback already active on same URL; skipping start.")
                return

            # If running on different URL, stop first
            if self._proc and self._proc.poll() is None and self._current_url != url:
                logging.info("Stopping playback to switch URL...")
                self._stop_proc_locked()

            # Reset control state
            self._stop_flag.clear()
            self._current_url = url
            self._retries = 0

            # Launch runner thread (detached control loop)
            if self._runner_thread and self._runner_thread.is_alive():
                # Should not happen, but ensure a clean one
                logging.debug("Old playback runner still alive; asking it to stop.")
                self._stop_flag.set()
                self._runner_thread.join(timeout=2)

            self._runner_thread = threading.Thread(
                target=self._run_loop, name="PlaybackRunner", daemon=True
            )
            self._runner_thread.start()
            logging.info("ffplay-based playback started in background.")

    def stop(self) -> None:
        """Stop playback and terminate process cleanly."""
        with self._lock:
            self._stop_flag.set()
            self._stop_proc_locked()

        # join thread outside lock
        if self._runner_thread and self._runner_thread.is_alive():
            self._runner_thread.join(timeout=5)
        self._runner_thread = None
        logging.info("Direct playback thread stopped.")

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
        """Owns the ffplay process; retries if it exits unexpectedly."""
        while not self._stop_flag.is_set():
            url = self.current_url()
            if not url:
                logging.warning("No URL set for playback; waiting...")
                time.sleep(1.0)
                continue

            args = [self.ffplay_path, *self.base_args, "-i", url]
            try:
                with self._lock:
                    # Spawn ffplay
                    logging.info(f"Using ffplay for direct playback: {url}")
                    self._proc = subprocess.Popen(args)

                # Wait for process to exit or stop requested
                while not self._stop_flag.is_set():
                    with self._lock:
                        proc = self._proc
                    if not proc:
                        break
                    rc = proc.poll()
                    if rc is None:
                        time.sleep(0.5)
                        continue
                    # Process exited
                    if rc == 0:
                        logging.info("ffplay exited naturally.")
                    else:
                        logging.warning("ffplay exited unexpectedly.")
                    break

            except FileNotFoundError:
                logging.error("ffplay not found. Ensure FFmpeg is installed and in PATH.")
                break
            except Exception as e:
                logging.exception(f"Error launching/monitoring ffplay: {e}")

            # Cleanup after exit
            with self._lock:
                self._stop_proc_locked()

            if self._stop_flag.is_set():
                break

            # Retry policy for unexpected exit
            self._retries += 1
            if self._retries > self.max_retries:
                logging.error("Playback failed too many times; giving up until URL changes.")
                break

            logging.info(
                f"Retrying playback in {self.retry_delay_sec:.0f}s (attempt {self._retries}/{self.max_retries})...")
            time.sleep(self.retry_delay_sec)

        # Final cleanup
        with self._lock:
            self._stop_proc_locked()

    def _stop_proc_locked(self) -> None:
        """Terminate current ffplay process (requires self._lock held)."""
        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
                # Clear handle regardless
            except Exception:
                pass
            finally:
                self._proc = None
