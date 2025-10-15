"""
Audio detection module.
Detects the start and end of Adhaan from livestream audio using FFmpeg and NumPy.
Includes:
 - Sustained loudness verification (2s) before confirming START.
 - Auto-calibration of threshold using ambient RMS.
 - Background ambient monitor to track live noise floor.
 - Audio snippet + CSV logging for diagnostics.
"""

import subprocess
import numpy as np
import logging
import threading
import time
import os
from typing import Optional
from utils.adhaan_logger import log_event

# === Global shared state ===
AMBIENT_STATE = {"rms": 0.0003, "running": False}
AUDIO_LOG_DIR = os.path.join("assets", "audio_logs")
os.makedirs(AUDIO_LOG_DIR, exist_ok=True)


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
                "-t", "2",  # record 2 seconds
                "-f", "wav", "pipe:1",
            ]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_audio = process.stdout.read(sample_rate * 2 * 2)  # 2 sec mono 16-bit
            process.terminate()

            if raw_audio:
                audio_data = np.frombuffer(raw_audio, dtype=np.int16)
                rms = np.sqrt(np.mean(np.square(audio_data / 32768.0)))
                peak = np.max(np.abs(audio_data)) / 32768.0
                db = 20 * np.log10(rms + 1e-8)

                AMBIENT_STATE["rms"] = rms
                logging.info(f"🎚️ Ambient RMS: {rms:.4f} | {db:.1f} dB | Peak: {peak:.4f}")

            time.sleep(10)  # wait before next sample

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


# === START DETECTION ===
def detect_audio_start(threshold: float = 0.05,
                       sample_rate: int = 44100,
                       stream_url: Optional[str] = None,
                       min_duration_above_threshold: float = 2.0) -> bool:
    """Detects Adhaan START after sustained volume for 2 s, auto-adjusting threshold."""
    logging.info("🎙️ Listening for Adhaan START in livestream audio...")

    ambient_rms = AMBIENT_STATE.get("rms", 0.0003)
    effective_threshold = max(ambient_rms * 3, threshold * 0.4)
    logging.info(f"🎚️ Ambient RMS baseline: {ambient_rms:.4f} | Adjusted threshold: {effective_threshold:.4f}")

    cmd = [
        "ffmpeg", "-i", stream_url if stream_url else "pipe:0",
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(sample_rate), "-ac", "1",
        "-f", "wav", "pipe:1",
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096)
    audio_buffer = bytearray()
    consecutive_high = 0.0
    bytes_per_second = sample_rate * 2

    try:
        while True:
            raw_audio = process.stdout.read(4096)
            if not raw_audio:
                if process.poll() is not None:
                    logging.warning("⚠️ FFmpeg stopped (start detection).")
                    break
                continue

            audio_buffer.extend(raw_audio)
            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                rms = np.sqrt(np.mean(np.square(audio_data / 32768.0)))
                peak = np.max(np.abs(audio_data)) / 32768.0
                db = 20 * np.log10(rms + 1e-8)

                if rms > effective_threshold:
                    consecutive_high += 1.0
                    logging.debug(
                        f"🔊 RMS={rms:.4f} | Peak={peak:.4f} | {db:.1f} dB | ↑ {consecutive_high:.1f}s > threshold")
                else:
                    consecutive_high = max(0.0, consecutive_high - 0.5)

                if consecutive_high >= min_duration_above_threshold:
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    snippet_path = os.path.join(AUDIO_LOG_DIR, f"adhaan_candidate_{timestamp}.wav")
                    with open(snippet_path, "wb") as f:
                        f.write(audio_chunk)
                    log_event("start", snippet_path, rms, db)
                    logging.info(f"✅ Adhaan START confirmed after {consecutive_high:.1f}s sustained volume")
                    logging.info(f"🎧 Saved snippet → {snippet_path}")
                    process.terminate()
                    return True

    except Exception as e:
        logging.exception(f"Error in start detection: {e}")
    finally:
        process.terminate()

    return False


# === END DETECTION ===
def detect_audio_end(threshold: float = 0.05,
                     sample_rate: int = 44100,
                     required_silence: int = 7,
                     stream_url: Optional[str] = None) -> bool:
    """Detects when Adhaan ends based on sustained silence."""
    logging.info("🎧 Listening for Adhaan END in livestream audio...")

    cmd = [
        "ffmpeg", "-i", stream_url if stream_url else "pipe:0",
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(sample_rate), "-ac", "1",
        "-f", "wav", "pipe:1",
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096)
    audio_buffer = bytearray()
    silence_counter = 0
    bytes_per_second = sample_rate * 2

    try:
        while True:
            raw_audio = process.stdout.read(4096)
            if not raw_audio:
                if process.poll() is not None:
                    logging.warning("⚠️ FFmpeg stopped (end detection).")
                    break
                continue

            audio_buffer.extend(raw_audio)
            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                rms = np.sqrt(np.mean(np.square(audio_data / 32768.0)))
                db = 20 * np.log10(rms + 1e-8)

                if rms < threshold:
                    silence_counter += 1
                else:
                    silence_counter = 0

                if silence_counter >= required_silence:
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    snippet_path = os.path.join(AUDIO_LOG_DIR, f"adhaan_candidate_{timestamp}.wav")
                    with open(snippet_path, "wb") as f:
                        f.write(audio_chunk)
                    log_event("end", snippet_path, rms, db)
                    logging.info(f"🔇 Sustained silence detected — Adhaan END.")
                    logging.info(f"🎧 Saved snippet → {snippet_path}")
                    process.terminate()
                    return True

    except Exception as e:
        logging.exception(f"Error in end detection: {e}")
    finally:
        process.terminate()

    return False


# === THREAD MANAGEMENT ===
_detection_thread = None
_detection_stop = threading.Event()


def _run_full_detection(stream_url: str):
    """Runs full start→end Adhaan detection pipeline."""
    global _detection_stop
    try:
        logging.info(f"🎧 Starting Adhaan detection sequence for stream: {stream_url}")
        start_time = time.strftime("%H:%M:%S")

        started = detect_audio_start(threshold=0.05, stream_url=stream_url)
        if not started or _detection_stop.is_set():
            logging.info("⏸️ No Adhaan start detected (or manually stopped).")
            return

        logging.info(f"🕌 Adhaan started at {start_time}")

        ended = detect_audio_end(threshold=0.05, required_silence=7, stream_url=stream_url)
        if ended:
            end_time = time.strftime("%H:%M:%S")
            logging.info(f"🏁 Adhaan ended at {end_time}")
        else:
            logging.info("⚠️ End not confirmed (process stopped or timed out).")

    except Exception as e:
        logging.exception(f"❌ Error in full detection thread: {e}")
    finally:
        logging.info("🛑 Full Adhaan detection thread stopped.")


def start_audio_detection(stream_url: str):
    """Starts full start→end detection in background."""
    global _detection_thread, _detection_stop
    stop_audio_detection()
    _detection_stop.clear()
    _detection_thread = threading.Thread(target=_run_full_detection, args=(stream_url,), daemon=True)
    _detection_thread.start()
    logging.info("🎙️ Adhaan start/end detection started in background.")


def stop_audio_detection():
    """Stops current Adhaan detection thread."""
    global _detection_thread, _detection_stop
    if _detection_thread and _detection_thread.is_alive():
        logging.info("🧹 Stopping Adhaan detection thread...")
        _detection_stop.set()
        _detection_thread.join(timeout=5)
    _detection_thread = None
