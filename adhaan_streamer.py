import time
import subprocess
import numpy as np
import sounddevice as sd
import pyaudio
from datetime import datetime
from util import get_prayer_times, get_m3u8_url
from tabulate import tabulate
import ffmpeg
import queue
import select
import os
import sys
import tempfile

# ✅ Livestream URL (replace with your updated tokenized URL)
LIVESTREAM_URL = "https://iaccplano.click2stream.com/"

AUD_VID_STREAM = get_m3u8_url(LIVESTREAM_URL)

# ✅ Prayers that trigger Adhaan
REQUIRED_PRAYERS = {"Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"}

# ✅ FFmpeg command to play livestream (Video + Audio)
FFMPEG_CMD = [
    "ffplay",
    "-i", AUD_VID_STREAM,
    "-loglevel", "quiet"  # Suppresses unnecessary logs
]

def display_prayer_times(prayer_times):
    """Displays all prayer times, separating Adhaan prayers from other times."""
    adhaan_times = []
    other_times = []

    for prayer, time_pt in prayer_times.items():
        formatted_time = time_pt.strftime("%I:%M %p")
        if prayer in REQUIRED_PRAYERS:
            adhaan_times.append([prayer, formatted_time])
        else:
            other_times.append([prayer, formatted_time])

    max_rows = max(len(adhaan_times), len(other_times))
    table = []

    for i in range(max_rows):
        adhaan_row = adhaan_times[i] if i < len(adhaan_times) else ["", ""]
        other_row = other_times[i] if i < len(other_times) else ["", ""]
        table.append(adhaan_row + other_row)

    headers = ["Adhaan Prayers", "Time", "Other Timings", "Time"]
    print("\n🕌 **Masjid Prayer Timings**\n" + tabulate(table, headers=headers, tablefmt="fancy_grid") + "\n")


def detect_audio_start(threshold=0.05, sample_rate=44100):
    """
    Detects the start of Adhaan from the livestream audio.
    - Uses FFmpeg to extract audio from the livestream.
    - Processes in-memory audio and detects Adhaan based on continuous loudness.
    - If detected, triggers livestream playback.
    """
    print("🎙️ Listening for Adhaan in livestream audio...")

    # ✅ Use a temporary file to prevent PIPE deadlock
    temp_audio = tempfile.TemporaryFile()

    # ✅ Start FFmpeg Process for Audio Extraction
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-i", AUD_VID_STREAM,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
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

    audio_buffer = bytearray()  # Store incoming audio data

    while True:
        try:
            if process.poll() is not None:
                print("⚠️ FFmpeg process stopped unexpectedly (start-detection).")
                break

            # ✅ Read audio in chunks
            temp_audio.seek(0)
            raw_audio = temp_audio.read(4096)
            temp_audio.truncate(0)

            if not raw_audio:
                continue

            audio_buffer.extend(raw_audio)

            # ✅ Process audio when we have 1 second worth of data
            bytes_per_second = sample_rate * 2 // 2  # 16-bit PCM (2 bytes per sample, 1 channel)
            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]  # Remove processed data

                # ✅ Convert to NumPy array for volume analysis
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                volume = np.max(np.abs(audio_data)) / 32768.0  # Normalize 16-bit

                print(f"🔊 Detected volume level (start-check): {volume:.2f}")

                # ✅ Count how many samples are above the threshold
                loud_samples = np.sum((np.abs(audio_data)/32768.0) > threshold)
                loud_duration = loud_samples / float(sample_rate)

                # If we have at least 1 second of loudness
                if loud_duration >= 0.001:
                    print("🔊 Adhaan detected in livestream! Playing video...")
                    process.terminate()
                    temp_audio.close()
                    return True

        except Exception as e:
            print(f"⚠️ Error reading audio data (start-detection): {e}")
            break

    process.terminate()
    temp_audio.close()
    return False


def detect_audio_end(threshold=0.05, sample_rate=44100, required_silence=7):
    """
    Detects the end of Adhaan from the livestream audio.
    - Uses a second FFmpeg process to extract audio from the same livestream.
    - Detects Adhaan end when volume remains below `threshold` for `required_silence` seconds.
    """
    print("🎙️ Listening for Adhaan END in livestream audio...")

    # ✅ Use a temporary file to prevent PIPE deadlock
    temp_audio = tempfile.TemporaryFile()

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-i", AUD_VID_STREAM,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
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
    consecutive_silence = 0.0  # Track how many seconds of continuous silence we have

    while True:
        try:
            if process.poll() is not None:
                print("⚠️ FFmpeg process stopped unexpectedly (end-detection).")
                break

            # ✅ Read audio in chunks
            temp_audio.seek(0)
            raw_audio = temp_audio.read(4096)
            temp_audio.truncate(0)

            if not raw_audio:
                continue

            audio_buffer.extend(raw_audio)

            # ✅ Process 1 second worth of data
            bytes_per_second = sample_rate * 2 // 2
            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]

                # ✅ Convert to NumPy array for volume analysis
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                volume = np.max(np.abs(audio_data)) / 32768.0

                print(f"🔊 Detected volume level (end-check): {volume:.2f}")

                if volume < threshold:
                    # Volume is below threshold => count as silence
                    consecutive_silence += 1.0
                else:
                    # Reset if we hear something louder
                    consecutive_silence = 0.0

                # If we've hit the required silence duration
                if consecutive_silence >= required_silence:
                    print("🔇 Adhaan is silent for enough time. Ending now...")
                    process.terminate()
                    temp_audio.close()
                    return True

        except Exception as e:
            print(f"⚠️ Error reading audio data (end-detection): {e}")
            break

    process.terminate()
    temp_audio.close()
    return False


def play_livestream():
    """Plays both video & audio from the livestream using FFmpeg."""
    print("🎥 Streaming Adhaan (Video + Audio)...")
    process = subprocess.Popen(FFMPEG_CMD)
    return process  # Return process so we can terminate it later


def check_prayer_time(prayer_times):
    """
    Continuously checks prayer times and starts livestream when Adhaan is detected.
    After Adhaan starts, waits until Adhaan ends (detected via silence) to stop.
    """
    while True:
        now = datetime.now().time()

        for prayer, prayer_time in prayer_times.items():
            if prayer in REQUIRED_PRAYERS and now.hour == prayer_time.hour and now.minute == prayer_time.minute:
                print(f"🕌 Waiting for Adhaan at {prayer_time.strftime('%I:%M %p')}...")

                # 1) Detect Adhaan Start
                if detect_audio_start():
                    # 2) Play Livestream
                    livestream_process = play_livestream()

                    # 3) Detect Adhaan End
                    ended = detect_audio_end()
                    if ended:
                        print("🔇 Stopping livestream...")
                        livestream_process.terminate()

                # Prevent immediate re-trigger for 5 minutes (adjust as needed)
                time.sleep(300)

        time.sleep(30)  # Check every 30 seconds


if __name__ == "__main__":
    print("📢 Adhaan notifier running... Fetching prayer times.")
    prayer_times = get_prayer_times()

    if prayer_times:
        display_prayer_times(prayer_times)
        check_prayer_time(prayer_times)  # ✅ Runs continuously
    else:
        print("⚠️ Failed to fetch prayer times. Exiting.")
