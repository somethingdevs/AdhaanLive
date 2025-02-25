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

    for prayer, time in prayer_times.items():
        formatted_time = time.strftime("%I:%M %p")
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
    Detects Adhaan from the livestream audio.
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
        bufsize=1024
    )

    audio_buffer = bytearray()  # Store incoming audio data

    while True:
        try:
            if process.poll() is not None:
                print("⚠️ FFmpeg process stopped unexpectedly.")
                break

            # ✅ Read audio in chunks (buffered approach)
            temp_audio.seek(0)
            raw_audio = temp_audio.read(1024)
            temp_audio.truncate(0)

            if not raw_audio:
                time.sleep(0.1)
                continue

            audio_buffer.extend(raw_audio)

            # ✅ Process audio when we have 1 second worth of data
            bytes_per_second = sample_rate * 2 // 2  # 16-bit PCM (2 bytes per sample)
            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]  # Remove processed data

                # ✅ Convert to NumPy array for volume analysis
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                volume = np.max(np.abs(audio_data)) / 32768.0  # Normalize

                print(f"🔊 Detected volume level: {volume:.2f}")  # Debugging

                # ✅ NEW: Check if enough continuous loud samples exist
                loud_samples = np.sum(audio_data / 32768.0 > threshold)  # Count loud samples
                loud_duration = loud_samples / sample_rate  # Convert to seconds

                if loud_duration >= 0.001:  # Adhaan is sustained for 1 second
                    print("🔊 Adhaan detected in livestream! Playing video...")
                    process.terminate()
                    temp_audio.close()
                    return True

        except Exception as e:
            print(f"⚠️ Error reading audio data: {e}")
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
    """Continuously checks prayer times and starts livestream when Adhaan is detected."""
    while True:
        now = datetime.now().time()

        for prayer, prayer_time in prayer_times.items():
            if True: #prayer in REQUIRED_PRAYERS and now.hour == prayer_time.hour and now.minute == prayer_time.minute:
                print(f"🕌 Waiting for Adhaan at {prayer_time.strftime('%I:%M %p')}...")
                
                # ✅ Start monitoring microphone for Adhaan
                if detect_audio_start():
                    livestream_process = play_livestream()
                    
                    # ✅ Wait for Adhaan to end
                    time.sleep(180)  # Assume Adhaan lasts max 5 mins CHANGE BACK TO 3 MINS
                    
                    # ✅ Stop livestream when Adhaan is over
                    print("🔇 Stopping livestream...")
                    livestream_process.terminate()
                
                time.sleep(300)  # Prevent immediate re-trigger for 5 minutes CHANGE BACK TO 5 MINS

        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    print("📢 Adhaan notifier running... Fetching prayer times.")
    prayer_times = get_prayer_times()

    if prayer_times:
        display_prayer_times(prayer_times)
        check_prayer_time(prayer_times)  # ✅ Runs continuously
    else:
        print("⚠️ Failed to fetch prayer times. Exiting.")
