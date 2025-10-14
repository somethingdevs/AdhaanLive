import requests
import logging
from datetime import datetime


def get_prayer_times(city: str, country: str, method: int) -> dict:
    """Fetch daily prayer times from the Aladhan API."""
    api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method={method}"
    logging.info(f"🕌 Fetching prayer times for {city}, {country}...")
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            name: datetime.strptime(time_str, "%H:%M").time()
            for name, time_str in data["data"]["timings"].items()
        }
    except Exception as e:
        logging.error(f"⚠️ Error fetching prayer times: {e}")
        return {}
