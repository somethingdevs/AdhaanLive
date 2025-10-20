"""
Audio detection module with full Adhaan session recording.
Detects start and end of Adhaan and records continuously
from the moment Adhaan begins until silence is detected.
"""

import subprocess
import numpy as np
import logging
import threading
import time
import os
import wave
from typing import Optional
from collections import deque
from utils.adhaan_logger import log_event

# === Global shared state ===
AMBIENT_STATE = {"rms": 0.0003, "db": -70.0, "peak": 0.0, "timestamp": None, "running": False}
_AMBIENT_LOCK = threading.Lock()
AUDIO_LOG_DIR = os.path.join("assets", "audio_logs")
os.makedirs(AUDIO_LOG_DIR, exist_ok=True)

# === Detection flags ===
_detection_thread = None
_detection_stop = threading.Event()
_detection_in_progress = threading.Event()

# === Adhaan activity state (used by refresher/watchdog) ===
_adhaan_active = False
_adhaan_lock = threading.Lock()


def mark_adhaan_active(active: bool):
    """Sets the global Adhaan activity flag (thread-safe)."""
    global _adhaan_active
    with _adhaan_lock:
        _adhaan_active = active
        logging.info(f"🕌 mark_adhaan_active({active})")


def is_adhaan_active() -> bool:
    """Returns True if Adhaan currently in progress (thread-safe)."""
    with _adhaan_lock:
        return _adhaan_active


def save_wav(snippet_path, audio_bytes, sample_rate=44100):
    """Properly wrap raw PCM data in a WAV container."""
    with wave.open(snippet_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)


# === AMBIENT MONITOR ===
def _ambient_monitor_loop(stream_url: str, sample_rate: int = 44100):
    """Continuously measures background RMS from livestream audio."""
    global AMBIENT_STATE
    AMBIENT_STATE["running"] = True

    while AMBIENT_STATE["running"]:
        try:
            cmd = [
                "ffmpeg",
                "-i", stream_url,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", str(sample_rate), "-ac", "1",
                "-t", "2",
                "-f", "wav", "pipe:1",
            ]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_audio = process.stdout.read(sample_rate * 2 * 2)
            process.terminate()

            if raw_audio:
                audio_data = np.frombuffer(raw_audio, dtype=np.int16)
                rms = np.sqrt(np.mean(np.square(audio_data / 32768.0)))
                peak = np.max(np.abs(audio_data)) / 32768.0
                db = 20 * np.log10(rms + 1e-8)

                with _AMBIENT_LOCK:
                    AMBIENT_STATE.update({
                        "rms": rms, "db": db, "peak": peak, "timestamp": time.time(),
                    })

                logging.info(f"🎚️ Ambient RMS: {rms:.4f} | {db:.1f} dB | Peak: {peak:.4f}")

            time.sleep(10)

        except Exception as e:
            logging.warning(f"⚠️ Ambient monitor error: {e}")
            time.sleep(10)

    logging.info("🛑 Ambient monitor stopped.")


def start_ambient_monitor(stream_url: str):
    """Start background ambient RMS monitor."""
    if AMBIENT_STATE.get("running"):
        logging.info("🔁 Ambient monitor already running.")
        return
    threading.Thread(target=_ambient_monitor_loop, args=(stream_url,), daemon=True).start()
    logging.info("🎧 Ambient monitor started in background.")


def stop_ambient_monitor():
    """Stop background ambient monitor."""
    AMBIENT_STATE["running"] = False


def get_ambient_snapshot() -> dict:
    """Return the latest ambient RMS/peak/db snapshot."""
    with _AMBIENT_LOCK:
        return dict(AMBIENT_STATE)


# === CONTINUOUS ADHAAN DETECTION & RECORDING ===
def _run_full_detection(stream_url: str, sample_rate: int = 44100):
    """Runs full start→end Adhaan detection pipeline with continuous recording."""
    global _detection_stop, _detection_in_progress
    try:
        _detection_in_progress.set()
        logging.info(f"🎧 Starting Adhaan detection for stream: {stream_url}")

        # --- Setup ---
        bytes_per_second = sample_rate * 2
        ambient_rms = AMBIENT_STATE.get("rms", 0.0003)
        threshold = max(ambient_rms * 3, 0.05)
        silence_threshold = threshold * 0.5
        required_silence = 7

        cmd = [
            "ffmpeg", "-i", stream_url,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "1",
            "-f", "wav", "pipe:1",
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096)

        # Buffers and state
        pre_buffer = deque(maxlen=5)
        recording = bytearray()
        adhaan_started = False
        silence_counter = 0
        consecutive_high = 0.0
        file_path = None

        while not _detection_stop.is_set():
            raw_audio = process.stdout.read(bytes_per_second)
            if not raw_audio:
                if process.poll() is not None:
                    logging.warning("⚠️ FFmpeg stopped.")
                    break
                continue

            pre_buffer.append(raw_audio)
            audio_data = np.frombuffer(raw_audio, dtype=np.int16)
            rms = np.sqrt(np.mean(np.square(audio_data / 32768.0)))
            db = 20 * np.log10(rms + 1e-8)

            if not adhaan_started:
                # waiting for loudness trigger
                if rms > threshold:
                    consecutive_high += 1
                else:
                    consecutive_high = max(0.0, consecutive_high - 0.5)

                if consecutive_high >= 2.0:
                    # === START DETECTED ===
                    adhaan_started = True
                    start_time = time.strftime("%H:%M:%S")
                    file_path = os.path.join(
                        AUDIO_LOG_DIR, f"adhaan_full_{time.strftime('%Y-%m-%d_%H-%M-%S')}.wav"
                    )
                    log_event("start", file_path, rms, db)
                    mark_adhaan_active(True)  # 🕌 Mark Adhaan as active
                    logging.info(f"✅ Adhaan START confirmed at {start_time} | RMS={rms:.4f} | dB={db:.1f}")
                    # include pre-buffer in recording
                    for chunk in pre_buffer:
                        recording.extend(chunk)
                    continue

            else:
                # already started; record continuously
                recording.extend(raw_audio)
                if rms < silence_threshold:
                    silence_counter += 1
                else:
                    silence_counter = 0

                if silence_counter >= required_silence:
                    # === END DETECTED ===
                    end_time = time.strftime("%H:%M:%S")
                    save_wav(file_path, recording, sample_rate)
                    log_event("end", file_path, rms, db)
                    mark_adhaan_active(False)  # 🕌 Mark Adhaan as inactive
                    logging.info(
                        f"🏁 Adhaan END detected at {end_time} (duration={len(recording) / (bytes_per_second):.1f}s)"
                    )
                    break

        process.terminate()

    except Exception as e:
        logging.exception(f"❌ Detection thread error: {e}")
    finally:
        _detection_in_progress.clear()
        mark_adhaan_active(False)  # 🕌 Always clear on thread exit (safety)
        logging.info("🛑 Full Adhaan detection thread stopped.")


def start_audio_detection(stream_url: str):
    """Starts full start→end detection in background."""
    global _detection_thread, _detection_stop, _detection_in_progress
    if _detection_in_progress.is_set():
        logging.info("⚙️ Detection already running — skipping new start.")
        return
    stop_audio_detection()
    _detection_stop.clear()
    _detection_thread = threading.Thread(target=_run_full_detection, args=(stream_url,), daemon=True)
    _detection_thread.start()
    logging.info("🎙️ Adhaan start→end detection started in background.")


def stop_audio_detection():
    """Stops current Adhaan detection thread."""
    global _detection_thread, _detection_stop, _detection_in_progress
    _detection_stop.set()
    if _detection_thread and _detection_thread.is_alive():
        logging.info("🧹 Stopping Adhaan detection thread...")
        _detection_thread.join(timeout=5)
    _detection_thread = None
    _detection_in_progress.clear()
    mark_adhaan_active(False)  # 🕌 ensure flag reset
