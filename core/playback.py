"""
Buffered live playback module.
Streams the Adhaan livestream with a small delay (≈2 s) using FFmpeg and sounddevice.
Now uses a persistent OutputStream to ensure continuous audible playback.
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
BUFFER_SECONDS = 1  # Playback delay
CHUNK_SIZE = 4096  # Bytes per read from FFmpeg
CHANNELS = 2

# === Global thread controls ===
_playback_thread = None
_playback_stop = threading.Event()


def reshape_audio_chunk(data: np.ndarray, channels: int) -> np.ndarray:
    """
    Takes a 1D int16 numpy array (raw PCM from FFmpeg) and returns a properly
    shaped 2D array of shape (frames, channels).
    If channels=1: returns (n,) or (n,1).
    If channels=2: tries stereo reshape; if input mono, upmix to stereo.
    """
    if channels == 1:
        return data  # writing mono directly works with stream

    # Try to reshape to stereo (if originally stereo)
    try:
        return data.reshape(-1, channels)
    except ValueError:
        # Upmix mono -> stereo by repeating columns
        mono = data.reshape(-1, 1)
        return np.repeat(mono, channels, axis=1)


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
        "-vn",
        "-ac", str(CHANNELS),  # Force stereo here
        "-acodec", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        "-f", "s16le",
        "pipe:1",
        "-loglevel", "quiet",
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=CHUNK_SIZE * 4)

    # === Persistent OutputStream setup ===
    try:
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',
            blocksize=CHUNK_SIZE // (2 * CHANNELS),
        )
        stream.start()
        logging.info("🔈 Audio OutputStream started successfully.")
    except Exception as e:
        logging.exception(f"❌ Failed to initialize OutputStream: {e}")
        process.terminate()
        return

    # --- Inner function: plays from queue continuously ---
    def playback_loop():
        while not _playback_stop.is_set():
            try:
                chunk = buffer_q.get(timeout=1)
                if not chunk:
                    continue

                # Convert raw bytes → NumPy array (interleaved if stereo)
                data = np.frombuffer(chunk, dtype=np.int16)
                frames = reshape_audio_chunk(data, CHANNELS)
                stream.write(frames)

            except queue.Empty:
                continue
            except Exception as e:
                logging.warning(f"⚠️ Playback error: {e}")
                time.sleep(0.2)

        logging.info("🔇 Playback loop exiting; stopping OutputStream.")
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

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

            # Drop oldest if buffer full (ensures rolling delay)
            if buffer_q.full():
                _ = buffer_q.get_nowait()
            buffer_q.put_nowait(chunk)

    except Exception as e:
        logging.exception(f"❌ Error in playback worker: {e}")
    finally:
        process.terminate()
        _playback_stop.set()
        player.join(timeout=3)
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
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
