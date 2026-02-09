# ================================
# detector.py — STATE-CENTRALIZED
# ================================

import subprocess
import numpy as np
import logging
import threading
import time
import os
from collections import deque
from typing import Optional

from utils.adhaan_logger import log_event
from utils.audio_logger import save_wav
from core.playback import PLAYBACK
from core.runtime_state import state

# -------------------------------
# CONFIG
# -------------------------------

SAMPLE_RATE = 44100
BYTES_PER_SECOND = SAMPLE_RATE * 2

ADHAAN_MAX_DURATION_SEC = 5 * 60
MAX_SILENCE_SEC = 10
TAIL_SEC = 6

THRESHOLD = 0.05
SILENCE_THRESHOLD = THRESHOLD * 0.5

AUDIO_LOG_DIR = os.path.join("assets", "audio_logs")
os.makedirs(AUDIO_LOG_DIR, exist_ok=True)

# -------------------------------
# THREAD CONTROL (local only)
# -------------------------------

_detection_thread: Optional[threading.Thread] = None
_detection_stop = threading.Event()
_detection_running = threading.Event()

# -------------------------------
# CORE DETECTION LOOP
# -------------------------------

def _run_detection(stream_url: str):
    process = None
    file_path = None
    total_bytes = 0

    try:
        _detection_running.set()
        state.start_detection()

        logging.info(f"[DETECT] Detection started | stream={stream_url}")

        cmd = [
            "ffmpeg", "-i", stream_url,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-f", "wav", "pipe:1",
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096,
        )

        pre_buffer = deque(maxlen=5)
        recording = bytearray()

        adhaan_started = False
        silence_counter = 0
        consecutive_high = 0.0
        start_ts = None
        empty_reads = 0

        while not _detection_stop.is_set():
            raw = process.stdout.read(BYTES_PER_SECOND)

            if not raw:
                empty_reads += 1
                if empty_reads > 10 and process.poll() is not None:
                    logging.warning("[DETECT] FFmpeg stalled")
                    break
                time.sleep(0.1)
                continue

            empty_reads = 0
            total_bytes += len(raw)
            pre_buffer.append(raw)

            audio = np.frombuffer(raw, dtype=np.int16)
            rms = np.sqrt(np.mean((audio / 32768.0) ** 2))
            db = 20 * np.log10(rms + 1e-8)

            # ---------- ADHAAN START ----------
            if not adhaan_started:
                consecutive_high = (
                    consecutive_high + 1 if rms > THRESHOLD
                    else max(0.0, consecutive_high - 0.5)
                )

                if consecutive_high >= 2.0:
                    adhaan_started = True
                    start_ts = time.time()

                    file_path = os.path.join(
                        AUDIO_LOG_DIR,
                        f"adhaan_{time.strftime('%Y-%m-%d_%H-%M-%S')}.wav"
                    )

                    log_event("start", file_path, rms, db)

                    state.start_adhaan()
                    PLAYBACK.start(stream_url)

                    for chunk in pre_buffer:
                        recording.extend(chunk)

                    logging.info("[DETECT] Adhaan detected")
                continue

            # ---------- RECORDING ----------
            recording.extend(raw)

            silence_counter = (
                silence_counter + 1 if rms < SILENCE_THRESHOLD else 0
            )

            if time.time() - start_ts >= ADHAAN_MAX_DURATION_SEC:
                silence_counter = MAX_SILENCE_SEC

            if silence_counter >= MAX_SILENCE_SEC:
                logging.info("[DETECT] Adhaan end (silence)")

                for _ in range(TAIL_SEC):
                    tail = process.stdout.read(BYTES_PER_SECOND)
                    if not tail:
                        break
                    recording.extend(tail)

                save_wav(file_path, recording)
                log_event("end", file_path, rms, db)

                state.end_adhaan()

                time.sleep(8)
                PLAYBACK.stop()
                break

    except Exception:
        logging.error("[DETECT] Failure", exc_info=True)

        # 🔒 SAFETY: never leave playback/adhaan running
        if state.playback_active:
            PLAYBACK.stop()

        if state.adhaan_active:
            state.end_adhaan()

    finally:
        if process:
            try:
                process.terminate()
            except Exception:
                pass

        # 🔒 FINAL GUARANTEE
        if state.playback_active:
            PLAYBACK.stop()

        log_event(
            "data_usage",
            file_path or "N/A",
            data_mb=total_bytes / 1e6,
        )

        state.stop_detection()
        _detection_running.clear()
        logging.info("[DETECT] Detection stopped")

# -------------------------------
# PUBLIC API
# -------------------------------

def start_audio_detection(stream_url: str):
    global _detection_thread

    if _detection_running.is_set():
        logging.info("[DETECT] Already running")
        return

    stop_audio_detection()
    _detection_stop.clear()

    _detection_thread = threading.Thread(
        target=_run_detection,
        args=(stream_url,),
        daemon=True,
    )
    _detection_thread.start()

    logging.info("[DETECT] Thread launched")


def stop_audio_detection():
    global _detection_thread

    _detection_stop.set()

    if _detection_thread and _detection_thread.is_alive():
        logging.info("[DETECT] Stopping thread")
        _detection_thread.join(timeout=5)

    _detection_thread = None
    _detection_running.clear()