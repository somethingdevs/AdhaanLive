import time
import webbrowser
from datetime import datetime
from util import get_prayer_times
from tabulate import tabulate  # Install using: pip install tabulate

# ✅ Set your mosque's livestream URL
LIVESTREAM_URL = "https://iaccplano.click2stream.com/"

# ✅ Prayers that trigger Adhaan
REQUIRED_PRAYERS = {"Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"}


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

    # Combine the two lists, aligning the display
    max_rows = max(len(adhaan_times), len(other_times))
    table = []

    for i in range(max_rows):
        adhaan_row = adhaan_times[i] if i < len(adhaan_times) else ["", ""]
        other_row = other_times[i] if i < len(other_times) else ["", ""]
        table.append(adhaan_row + other_row)

    headers = ["Adhaan Prayers", "Time", "Other Timings", "Time"]

    print("\n🕌 **Masjid Prayer Timings**\n" + tabulate(table, headers=headers, tablefmt="fancy_grid") + "\n")


def check_prayer_time(prayer_times):
    """Continuously checks the current time and opens the livestream only for required prayers."""
    while True:
        now = datetime.now().time()

        for prayer, prayer_time in prayer_times.items():
            if prayer in REQUIRED_PRAYERS and now.hour == prayer_time.hour and now.minute == prayer_time.minute:
                print(f"🔔 Playing Adhaan for {prayer} at {prayer_time.strftime('%I:%M %p')}...")
                webbrowser.open(LIVESTREAM_URL)
                time.sleep(60)  # Prevent multiple triggers for the same prayer

        time.sleep(30)  # Check every 30 seconds


if __name__ == "__main__":
    print("📢 Adhaan notifier running... Fetching prayer times.")
    prayer_times = get_prayer_times()

    if prayer_times:
        display_prayer_times(prayer_times)  # Show all prayer times with separation
        check_prayer_time(prayer_times)
    else:
        print("⚠️ Failed to fetch prayer times. Exiting.")
