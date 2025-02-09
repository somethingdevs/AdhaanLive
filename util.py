import requests
from datetime import datetime


def get_prayer_times(city="Dallas", country="US", method=2):
    """
    Fetches prayer times from Aladhan API and converts them into datetime.time objects.
    """
    api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method={method}"

    response = requests.get(api_url, timeout=10000)
    data = response.json()

    if response.status_code == 200:
        return {
            name: datetime.strptime(time_str, "%H:%M").time()
            for name, time_str in data["data"]["timings"].items()
        }
    else:
        print("⚠️ Error fetching prayer times!")
        return None
