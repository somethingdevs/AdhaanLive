"""
Buffered live playback module.
Streams the Adhaan livestream with a small delay (≈2 s) using FFmpeg and sounddevice.
"""

import subprocess
import threading
import queue
import numpy as np
import logging
import sounddevice as sd
import time

# === Configuration ===
SAMPLE_RATE = 44100
BUFFER_SECONDS = 2  # Playback delay
CHUNK_SIZE = 4096  # Bytes per read from FFmpeg
PLAYBACK_LATENCY = 0.1  # Seconds per audio write
CHANNELS = 1

# === Global thread controls ===
_playback_thread = None
_playback_stop = threading.Event()


def _playback_worker(stream_url: str):
    """Continuously read from FFmpeg and play through speakers with a rolling buffer."""
    global _playback_stop

    logging.info(f"🎧 Starting buffered live playback for: {stream_url}")

    # Thread-safe audio queue: holds about 2 s of audio
    buffer_q = queue.Queue(maxsize=int((SAMPLE_RATE * 2 * BUFFER_SECONDS) / CHUNK_SIZE))

    # FFmpeg: output 16-bit mono PCM
    cmd = [
        "ffmpeg",
        "-i", stream_url,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS),
        "-f", "s16le", "pipe:1",
        "-loglevel", "quiet",
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=CHUNK_SIZE * 4)

    # --- Inner function: plays from queue ---
    def playback_loop():
        logging.info("🔈 Playback thread ready (low-latency buffer active).")
        while not _playback_stop.is_set():
            try:
                chunk = buffer_q.get(timeout=1)
                if chunk:
                    # Convert raw bytes → NumPy array
                    audio_data = np.frombuffer(chunk, dtype=np.int16)
                    sd.play(audio_data, samplerate=SAMPLE_RATE, blocking=True)
            except queue.Empty:
                continue
            except Exception as e:
                logging.warning(f"⚠️ Playback error: {e}")
                time.sleep(0.5)

        sd.stop()
        logging.info("🔇 Playback thread stopped cleanly.")

    # Start playback thread
    player = threading.Thread(target=playback_loop, daemon=True)
    player.start()

    try:
        while not _playback_stop.is_set():
            chunk = process.stdout.read(CHUNK_SIZE)
            if not chunk:
                if process.poll() is not None:
                    logging.warning("⚠️ FFmpeg ended — playback stopped.")
                    break
                continue

            # Drop oldest if buffer full (ensures rolling 2 s delay)
            if buffer_q.full():
                _ = buffer_q.get_nowait()
            buffer_q.put_nowait(chunk)

    except Exception as e:
        logging.exception(f"❌ Error in playback worker: {e}")
    finally:
        process.terminate()
        _playback_stop.set()
        player.join(timeout=3)
        sd.stop()
        logging.info("🛑 Buffered playback fully stopped.")


def start_buffered_playback(stream_url: str):
    """Launches background playback thread."""
    global _playback_thread, _playback_stop
    stop_buffered_playback()  # ensure single instance
    _playback_stop.clear()

    _playback_thread = threading.Thread(target=_playback_worker, args=(stream_url,), daemon=True)
    _playback_thread.start()
    logging.info("🎙️ Buffered playback started in background.")


def stop_buffered_playback():
    """Stops live playback if active."""
    global _playback_thread, _playback_stop
    if _playback_thread and _playback_thread.is_alive():
        logging.info("🧹 Stopping buffered playback thread...")
        _playback_stop.set()
        _playback_thread.join(timeout=5)
    _playback_thread = None
