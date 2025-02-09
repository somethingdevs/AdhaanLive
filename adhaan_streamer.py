import time
import webbrowser
from datetime import datetime
from util import get_prayer_times
from tabulate import tabulate  # Install using: pip install tabulate

# 🔗 Set your mosque's livestream URL here
LIVESTREAM_URL = "https://iaccplano.click2stream.com/"
webbrowser.open(LIVESTREAM_URL)


def display_prayer_times(prayer_times):
    """Displays prayer times in a neat table format."""
    table = [[prayer, time.strftime("%I:%M %p")] for prayer, time in prayer_times.items()]
    print("\n🕌 Masjid Prayer Timings\n" + tabulate(table, headers=["Prayer", "Time"], tablefmt="fancy_grid") + "\n")


def check_prayer_time(prayer_times):
    """Continuously checks the current time and opens the live stream when it's Adhaan time."""
    while True:
        now = datetime.now().time()

        for prayer, prayer_time in prayer_times.items():
            if now.hour == prayer_time.hour and now.minute == prayer_time.minute:
                print(f"🔔 Playing Adhaan for {prayer} at {prayer_time.strftime('%I:%M %p')}...")
                webbrowser.open(LIVESTREAM_URL)
                time.sleep(60)  # Prevent multiple triggers

        time.sleep(30)  # Check every 30 seconds


if __name__ == "__main__":
    print("📢 Adhaan notifier running... Fetching prayer times.")
    prayer_times = get_prayer_times()

    if prayer_times:
        display_prayer_times(prayer_times)  # Show prayer times
        check_prayer_time(prayer_times)
    else:
        print("⚠️ Failed to fetch prayer times. Exiting.")
