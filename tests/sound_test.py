import subprocess
import numpy as np
import tempfile
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# Replace with your current livestream URL
LIVESTREAM_URL = "https://iaccplano.click2stream.com/"

# Sensitivity threshold — lower = more sensitive
THRESHOLD = 0.05
SAMPLE_RATE = 44100


def test_audio_detection():
    """Continuously listens to livestream audio and logs loud activity."""
    logging.info("🎧 Starting audio detection test...")
    temp_audio = tempfile.TemporaryFile()

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-i", LIVESTREAM_URL,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE),
            "-ac", "1",
            "-f", "wav",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-flush_packets", "1",
            "pipe:1"
        ],
        stdout=temp_audio,
        stderr=subprocess.DEVNULL,
        bufsize=4096
    )

    audio_buffer = bytearray()
    detected_once = False

    try:
        while True:
            if process.poll() is not None:
                logging.warning("⚠️ FFmpeg process exited unexpectedly.")
                break

            temp_audio.seek(0)
            raw_audio = temp_audio.read(4096)
            temp_audio.truncate(0)

            if not raw_audio:
                continue

            audio_buffer.extend(raw_audio)
            bytes_per_second = SAMPLE_RATE * 2 // 2  # 16-bit PCM mono

            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)

                volume = np.max(np.abs(audio_data)) / 32768.0
                if volume > THRESHOLD:
                    if not detected_once:
                        logging.info(f"🔊 Loud audio detected! Volume={volume:.2f}")
                        detected_once = True
                    else:
                        logging.debug(f"Audio active, volume={volume:.2f}")
                else:
                    logging.debug(f"Silent frame, volume={volume:.2f}")
            time.sleep(0.1)

    except KeyboardInterrupt:
        logging.info("🛑 Detection test stopped manually.")
    finally:
        process.terminate()
        temp_audio.close()


if __name__ == "__main__":
    test_audio_detection()
