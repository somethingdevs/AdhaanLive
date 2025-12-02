# ================================
# detector.py — CLEAN LOG VERSION
# ================================

import subprocess
import numpy as np
import logging
import threading
import time
import os
import wave
from collections import deque

from utils.adhaan_logger import log_event
from core.playback import PLAYBACK

# -------------------------------
# GLOBAL STATE
# -------------------------------

ADHAAN_MAX_DURATION_SEC = 5 * 60  # 5 min cap

_detection_thread = None
_detection_stop = threading.Event()
_detection_in_progress = threading.Event()

_adhaan_active = False
_adhaan_lock = threading.Lock()

AUDIO_LOG_DIR = os.path.join("assets", "audio_logs")
os.makedirs(AUDIO_LOG_DIR, exist_ok=True)


# -------------------------------
# ADHAAN ACTIVE FLAG
# -------------------------------

def mark_adhaan_active(active: bool):
    global _adhaan_active
    with _adhaan_lock:
        _adhaan_active = active
        logging.info(f"[DETECT] Active={active}")


def is_adhaan_active() -> bool:
    with _adhaan_lock:
        return _adhaan_active


# -------------------------------
# WAV WRITER
# -------------------------------

def save_wav(path, audio_bytes, sample_rate=44100):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)


# -------------------------------
# DETECTION CORE LOOP
# -------------------------------

def _run_full_detection(stream_url: str, sample_rate: int = 44100):
    total_bytes = 0

    try:
        _detection_in_progress.set()
        logging.info(f"[DETECT] Starting detection | stream={stream_url}")

        bytes_per_second = sample_rate * 2
        threshold = 0.05
        silence_threshold = threshold * 0.5

        MAX_SILENCE_SEC = 10
        TAIL_SEC = 6

        cmd = [
            "ffmpeg", "-i", stream_url,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "1",
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
        file_path = None
        start_ts = None
        empty_reads = 0

        while not _detection_stop.is_set():

            raw_audio = process.stdout.read(bytes_per_second)
            if not raw_audio:
                empty_reads += 1
                if empty_reads > 10 and process.poll() is not None:
                    logging.warning("[DETECT] FFmpeg became unresponsive")
                    break
                time.sleep(0.1)
                continue
            empty_reads = 0

            total_bytes += len(raw_audio)
            pre_buffer.append(raw_audio)

            audio_data = np.frombuffer(raw_audio, dtype=np.int16)
            rms = np.sqrt(np.mean(np.square(audio_data / 32768.0)))
            db = 20 * np.log10(rms + 1e-8)

            # ---------- START DETECTION ----------
            if not adhaan_started:

                if rms > threshold:
                    consecutive_high += 1
                else:
                    consecutive_high = max(0.0, consecutive_high - 0.5)

                if consecutive_high >= 2.0:
                    adhaan_started = True
                    start_ts = time.time()

                    file_path = os.path.join(
                        AUDIO_LOG_DIR,
                        f"adhaan_full_{time.strftime('%Y-%m-%d_%H-%M-%S')}.wav"
                    )

                    logging.info(f"[DETECT] START | rms={rms:.4f}, db={db:.1f}")
                    log_event("start", file_path, rms, db)
                    mark_adhaan_active(True)

                    PLAYBACK.start(stream_url)

                    for chunk in pre_buffer:
                        recording.extend(chunk)

                    continue

            # ---------- RECORDING IN PROGRESS ----------
            else:
                recording.extend(raw_audio)

                if rms < silence_threshold:
                    silence_counter += 1
                else:
                    silence_counter = 0

                elapsed = time.time() - start_ts
                if elapsed >= ADHAAN_MAX_DURATION_SEC:
                    logging.info("[DETECT] Max duration reached")
                    silence_counter = MAX_SILENCE_SEC

                if silence_counter >= MAX_SILENCE_SEC:
                    logging.info(f"[DETECT] Silence detected ({silence_counter}s)")

                    for _ in range(TAIL_SEC):
                        tail = process.stdout.read(bytes_per_second)
                        if not tail:
                            break
                        recording.extend(tail)

                    save_wav(file_path, recording, sample_rate)
                    duration = len(recording) / bytes_per_second

                    log_event("end", file_path, rms, db)
                    logging.info(f"[DETECT] END | duration={duration:.1f}s")

                    mark_adhaan_active(False)

                    time.sleep(8)
                    PLAYBACK.stop()

                    break

        process.terminate()

    except Exception as e:
        logging.error(f"[ERROR] Detection failure: {e}", exc_info=True)

    finally:
        total_mb = total_bytes / 1e6
        log_event("data_usage", file_path or "N/A", data_mb=total_mb)
        _detection_in_progress.clear()
        mark_adhaan_active(False)
        logging.info("[DETECT] Detection thread stopped")


# -------------------------------
# PUBLIC START/STOP
# -------------------------------

def start_audio_detection(stream_url: str):
    global _detection_thread

    if _detection_in_progress.is_set():
        logging.info("[DETECT] Already running")
        return

    stop_audio_detection()

    _detection_stop.clear()
    _detection_thread = threading.Thread(
        target=_run_full_detection,
        args=(stream_url,),
        daemon=True
    )
    _detection_thread.start()

    logging.info("[DETECT] Thread started")


def stop_audio_detection():
    global _detection_thread

    _detection_stop.set()

    if _detection_thread and _detection_thread.is_alive():
        logging.info("[DETECT] Stopping thread...")
        _detection_thread.join(timeout=5)

    _detection_thread = None
    _detection_in_progress.clear()
    mark_adhaan_active(False)
