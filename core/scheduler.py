"""
Schedules prayer checks and triggers Adhaan detection.
"""

import time
import logging
from datetime import datetime
from core.detector import start_audio_detection, stop_audio_detection
from core.player import play_livestream, stop_livestream


def check_prayer_time(prayer_times: dict, stream_url: str) -> None:
    """Continuously checks prayer times and handles adhaan start/end detection."""
    logging.info("📅 Starting prayer time scheduler...")
    required_prayers = {"Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"}

    while True:
        now = datetime.now().time()

        for prayer, prayer_time in prayer_times.items():
            if prayer in required_prayers and now.hour == prayer_time.hour and now.minute == prayer_time.minute:
                logging.info(f"🕌 Detected {prayer} time ({prayer_time.strftime('%I:%M %p')}).")

                if start_audio_detection():
                    process = play_livestream(stream_url)
                    if stop_audio_detection():
                        stop_livestream(process)

                time.sleep(300)  # Avoid retriggering
        time.sleep(30)
