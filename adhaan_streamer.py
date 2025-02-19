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

def detect_audio_start(threshold=0, duration=2, sample_rate=44100):
    """
    Detects Adhaan from the livestream audio.
    - Uses FFmpeg to extract audio from the livestream.
    - Reads the stream and processes volume levels in real-time.
    - Triggers when a sustained loud sound (Adhaan) is detected.
    """
    print("🎙️ Listening for Adhaan in livestream audio...")

    # ✅ Start FFmpeg Process for Audio Extraction
    process = (
        ffmpeg
        .input(AUD_VID_STREAM, format="hls", rtsp_transport="tcp")  # Ensure stable TCP transport
        .output('pipe:', format='wav', acodec='pcm_s16le', ac=1, ar=sample_rate)
        .global_args('-re')  # Read input in real-time to match playback speed
        .global_args('-fflags', 'nobuffer')  # Reduce latency
        .global_args('-flags', 'low_delay')  # Enable low latency mode
        .global_args('-probesize', '100M')  # Increase probe size to detect audio faster
        .global_args('-analyzeduration', '100M')  # Extend analysis duration
        .global_args('-loglevel', 'error')  # Minimize logging unless there's an error
        .run_async(pipe_stdout=True, pipe_stderr=subprocess.PIPE)
    )

    start_time = None

    while True:
        # ✅ Read raw audio data
        raw_audio = process.stdout.read(4096)  # Read 4096 bytes of audio
        if not raw_audio:
            print("⚠️ No audio data received. Retrying...")
            time.sleep(1)
            continue

        # ✅ Convert to NumPy array for volume analysis
        audio_data = np.frombuffer(raw_audio, dtype=np.int16)
        volume = np.max(np.abs(audio_data)) / 32768.0  # Normalize to range 0-1

        print(f"🔊 Detected volume level: {volume:.2f}")  # Debugging

        if volume > threshold:
            if start_time is None:
                start_time = time.time()
            elif time.time() - start_time >= duration:
                print("🔊 Adhaan detected in livestream! Playing video...")
                process.terminate()
                return True
        else:
            start_time = None  # Reset detection timer if volume drops

        time.sleep(0.5)

    # ✅ Ensure the FFmpeg process is terminated on exit
    process.terminate()
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
                    time.sleep(300)  # Assume Adhaan lasts max 5 mins
                    
                    # ✅ Stop livestream when Adhaan is over
                    print("🔇 Stopping livestream...")
                    livestream_process.terminate()
                
                time.sleep(180)  # Prevent immediate re-trigger for 5 minutes

        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    print("📢 Adhaan notifier running... Fetching prayer times.")
    prayer_times = get_prayer_times()

    if prayer_times:
        display_prayer_times(prayer_times)
        check_prayer_time(prayer_times)  # ✅ Runs continuously
    else:
        print("⚠️ Failed to fetch prayer times. Exiting.")
