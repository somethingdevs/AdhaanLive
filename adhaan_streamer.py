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
import threading
import argparse

# -------------------------------
# 🧪 CLI ARGUMENT PARSER
# -------------------------------
parser = argparse.ArgumentParser(description="Adhaan Streamer — detects Adhaan and plays livestream or test audio.")
parser.add_argument("--test", action="store_true",
                    help="Run in test mode using local Adhaan MP3 instead of livestream.")
args = parser.parse_args()

# ✅ Local Adhaan test file
TEST_AUDIO_FILE = "assets/adhaan-1.mp3"

# ✅ Livestream URL (replace with your updated tokenized URL)
LIVESTREAM_URL = "https://iaccplano.click2stream.com/"
AUD_VID_STREAM = get_m3u8_url(LIVESTREAM_URL)

# ✅ Prayers that trigger Adhaan
REQUIRED_PRAYERS = {"Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"}


# -----------------------------------------
# 🔊 AUDIO PLAYBACK HANDLER
# -----------------------------------------
def play_audio(source_url=None):
    """Plays either test audio or livestream depending on --test flag."""
    if args.test:
        if not os.path.exists(TEST_AUDIO_FILE):
            print(f"❌ Test audio file '{TEST_AUDIO_FILE}' not found.")
            return
        print("🧪 Test mode enabled — playing local Adhaan audio...")
        subprocess.run(["ffplay", "-nodisp", "-autoexit", TEST_AUDIO_FILE])
    else:
        if not source_url:
            print("⚠️ No stream URL provided for playback.")
            return
        print(f"🎥 Streaming Adhaan (Video + Audio) using URL:\n{source_url}")
        subprocess.run(["ffplay", "-i", source_url, "-loglevel", "error", "-autoexit"])


# -----------------------------------------
# 🔁 STREAM REFRESHER
# -----------------------------------------
def refresh_stream_url():
    """Refreshes the stream URL every 10 minutes to avoid expiration."""
    global AUD_VID_STREAM
    while True:
        time.sleep(600)  # Refresh every 10 minutes
        new_url = get_m3u8_url(LIVESTREAM_URL)
        if new_url:
            AUD_VID_STREAM = new_url
            print("🔄 Stream URL refreshed in background!")


# -----------------------------------------
# 🕌 DISPLAY PRAYER TIMES
# -----------------------------------------
def display_prayer_times(prayer_times):
    """Displays all prayer times, separating Adhaan prayers from other times."""
    adhaan_times, other_times = [], []

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


# -----------------------------------------
# 🎧 AUDIO DETECTION HELPERS
# -----------------------------------------
def detect_audio_start(threshold=0.05, sample_rate=44100):
    """Detects start of Adhaan from livestream audio."""
    if args.test:
        print("🧪 Test mode active — skipping audio detection.")
        return True

    print("🎙️ Listening for Adhaan in livestream audio...")
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
    while True:
        try:
            if process.poll() is not None:
                print("⚠️ FFmpeg process stopped unexpectedly (start-detection).")
                break

            temp_audio.seek(0)
            raw_audio = temp_audio.read(4096)
            temp_audio.truncate(0)
            if not raw_audio:
                continue

            audio_buffer.extend(raw_audio)
            bytes_per_second = sample_rate * 2 // 2

            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                volume = np.max(np.abs(audio_data)) / 32768.0

                print(f"🔊 Detected volume level (start-check): {volume:.2f}")
                if volume > threshold:
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
    """Detects end of Adhaan when livestream audio becomes silent."""
    if args.test:
        print("🧪 Test mode active — skipping end detection.")
        return True

    print("🎙️ Listening for Adhaan END in livestream audio...")
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
    consecutive_silence = 0.0

    while True:
        try:
            if process.poll() is not None:
                print("⚠️ FFmpeg process stopped unexpectedly (end-detection).")
                break

            temp_audio.seek(0)
            raw_audio = temp_audio.read(4096)
            temp_audio.truncate(0)
            if not raw_audio:
                continue

            audio_buffer.extend(raw_audio)
            bytes_per_second = sample_rate * 2 // 2

            if len(audio_buffer) >= bytes_per_second:
                audio_chunk = audio_buffer[:bytes_per_second]
                del audio_buffer[:bytes_per_second]
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                volume = np.max(np.abs(audio_data)) / 32768.0

                print(f"🔊 Detected volume level (end-check): {volume:.2f}")
                if volume < threshold:
                    consecutive_silence += 1.0
                else:
                    consecutive_silence = 0.0

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


# -----------------------------------------
# ⏰ MAIN PRAYER CHECK LOOP
# -----------------------------------------
def check_prayer_time(prayer_times):
    """Continuously checks prayer times and triggers playback at Adhaan."""
    while True:
        now = datetime.now().time()
        for prayer, prayer_time in prayer_times.items():
            if prayer in REQUIRED_PRAYERS and now.hour == prayer_time.hour and now.minute == prayer_time.minute:
                print(f"🕌 Waiting for Adhaan at {prayer_time.strftime('%I:%M %p')}...")
                if detect_audio_start():
                    play_audio(AUD_VID_STREAM)
                    detect_audio_end()
                time.sleep(300)
        time.sleep(30)


# -----------------------------------------
# 🏁 MAIN ENTRY POINT
# -----------------------------------------
if __name__ == "__main__":
    print("📢 Adhaan notifier running... Fetching prayer times.")
    prayer_times = get_prayer_times()
    threading.Thread(target=refresh_stream_url, daemon=True).start()

    if prayer_times:
        display_prayer_times(prayer_times)
        if args.test:
            play_audio()  # immediate local test playback
        else:
            check_prayer_time(prayer_times)
    else:
        print("⚠️ Failed to fetch prayer times. Exiting.")
