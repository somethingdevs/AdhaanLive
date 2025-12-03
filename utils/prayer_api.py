# --- CLEAN LOGGING VERSION OF prayer_api.py ---

import requests
import logging
from datetime import datetime


def get_prayer_times(city: str, country: str, method: int) -> dict:
    """Fetch daily prayer times from Aladhan API."""
    api_url = (
        f"https://api.aladhan.com/v1/timingsByCity"
        f"?city={city}&country={country}&method={method}"
    )

    logging.info(f"[PRAYER] Fetching prayer times ({city}, {country})")

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        salah = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

        times = {
            name: datetime.strptime(time_str, "%H:%M").time()
            for name, time_str in data["data"]["timings"].items()
            if name in salah
        }

        return times

    except Exception as e:
        logging.error(f"[PRAYER] Failed to fetch prayer times: {e}")
        return {}
