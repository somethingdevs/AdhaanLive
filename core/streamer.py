"""
Main orchestrator module.
Initializes config, logs, threads, and starts the Adhaan streamer service.
"""

import threading
import time
import logging
from tabulate import tabulate
from utils import load_config, get_prayer_times, get_m3u8_url
from core.scheduler import check_prayer_time


def refresh_stream_url(base_url: str, refresh_interval: int = 600) -> None:
    """Refresh livestream URL periodically (handles expiring tokens)."""
    global STREAM_URL
    while True:
        time.sleep(refresh_interval)
        new_url = get_m3u8_url(base_url)
        if new_url:
            STREAM_URL = new_url
            logging.info("🔄 Stream URL refreshed successfully.")


def display_prayer_times(prayer_times: dict) -> None:
    """Pretty-print prayer times in a formatted table."""
    adhaan = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    other = ["Sunrise", "Sunset", "Imsak", "Midnight"]

    adhaan_rows = [[p, prayer_times.get(p)] for p in adhaan if p in prayer_times]
    other_rows = [[p, prayer_times.get(p)] for p in other if p in prayer_times]

    table = [
        adhaan_rows[i] + other_rows[i] if i < len(other_rows) else adhaan_rows[i] + ["", ""]
        for i in range(max(len(adhaan_rows), len(other_rows)))
    ]

    print("\n🕌 Prayer Timings\n" + tabulate(table, headers=["Adhaan", "Time", "Other", "Time"], tablefmt="fancy_grid"))


def start_streamer(test_mode: bool = False) -> None:
    """Main entry point for the Adhaan Streamer."""
    config = load_config()
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    city = config["settings"]["city"]
    country = config["settings"]["country"]
    method = config["settings"]["method"]
    livestream_url = config["livestream"]["url"]

    logging.info("📢 Starting Adhaan Streamer...")
    prayer_times = get_prayer_times(city, country, method)
    display_prayer_times(prayer_times)

    # Refresh livestream token every 10 minutes
    threading.Thread(target=refresh_stream_url, args=(livestream_url,), daemon=True).start()

    # Test mode: play local mp3
    if test_mode:
        logging.info("🧪 Test mode: Skipping detection. Playing local adhaan.mp3")
        import subprocess
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "assets/adhaan-1.mp3"])
        return

    check_prayer_time(prayer_times, livestream_url)
