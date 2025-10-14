"""
Audio detection module.
Detects the start and end of Adhaan from livestream audio using FFmpeg and NumPy.
"""

import subprocess
import numpy as np
import tempfile
import logging


def detect_audio_start(threshold: float = 0.05, sample_rate: int = 44100) -> bool:
    """Detects when Adhaan starts based on continuous loudness."""
    logging.info("🎙️ Listening for Adhaan START in livestream audio...")

    temp_audio = tempfile.TemporaryFile()
    process = subprocess.Popen(
        [
            "ffmpeg", "-i", "pipe:0",
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "1",
            "-f", "wav", "pipe:1",
        ],
        stdin=subprocess.DEVNULL,
        stdout=temp_audio,
        stderr=subprocess.DEVNULL,
        bufsize=4096,
    )

    audio_buffer = bytearray()
    try:
        while True:
            if process.poll() is not None:
                logging.warning("⚠️ FFmpeg process stopped (start detection).")
                break

            temp_audio.seek(0)
            raw_audio = temp_audio.read(4096)
            temp_audio.truncate(0)
            if not raw_audio:
                continue

            audio_buffer.extend(raw_audio)
            bytes_per_second = sample_rate * 2  # 16-bit mono PCM

            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]

                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                volume = np.max(np.abs(audio_data)) / 32768.0
                logging.debug(f"🔊 Volume (start): {volume:.3f}")

                if volume > threshold:
                    logging.info("✅ Adhaan detected in livestream.")
                    process.terminate()
                    return True

    except Exception as e:
        logging.exception(f"Error in start detection: {e}")
    finally:
        temp_audio.close()
        process.terminate()

    return False


def detect_audio_end(threshold: float = 0.05, sample_rate: int = 44100, required_silence: int = 7) -> bool:
    """Detects when Adhaan ends based on sustained silence."""
    logging.info("🎧 Listening for Adhaan END in livestream audio...")

    temp_audio = tempfile.TemporaryFile()
    process = subprocess.Popen(
        [
            "ffmpeg", "-i", "pipe:0",
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "1",
            "-f", "wav", "pipe:1",
        ],
        stdin=subprocess.DEVNULL,
        stdout=temp_audio,
        stderr=subprocess.DEVNULL,
        bufsize=4096,
    )

    audio_buffer = bytearray()
    silence_counter = 0.0

    try:
        while True:
            if process.poll() is not None:
                logging.warning("⚠️ FFmpeg process stopped (end detection).")
                break

            temp_audio.seek(0)
            raw_audio = temp_audio.read(4096)
            temp_audio.truncate(0)
            if not raw_audio:
                continue

            audio_buffer.extend(raw_audio)
            bytes_per_second = sample_rate * 2

            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]

                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                volume = np.max(np.abs(audio_data)) / 32768.0
                logging.debug(f"🔈 Volume (end): {volume:.3f}")

                if volume < threshold:
                    silence_counter += 1
                else:
                    silence_counter = 0

                if silence_counter >= required_silence:
                    logging.info("🔇 Detected sustained silence. Adhaan ended.")
                    process.terminate()
                    return True

    except Exception as e:
        logging.exception(f"Error in end detection: {e}")
    finally:
        temp_audio.close()
        process.terminate()

    return False
