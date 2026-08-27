import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from utils.config_loader import PrayerSettings


PRAYER_NAMES = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")
ALADHAN_URL = "https://api.aladhan.com/v1/timingsByCity/{date}"


def get_prayer_times(
    settings: PrayerSettings,
    now: Optional[datetime] = None,
) -> dict:
    """Fetch a timezone-aware daily prayer schedule from Aladhan."""
    mosque_zone = ZoneInfo(settings.timezone)
    reference_now = now or datetime.now(timezone.utc)
    if reference_now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    mosque_date = reference_now.astimezone(mosque_zone).date()
    api_url = ALADHAN_URL.format(date=mosque_date.strftime("%d-%m-%Y"))
    params = {
        "city": settings.city,
        "country": settings.country,
        "method": settings.method,
        "school": settings.school,
    }

    logging.info(
        "[PRAYER] Fetching prayer times (%s, %s, %s)",
        settings.city,
        settings.country,
        settings.timezone,
    )

    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        prayer_data = data["data"]
        api_timezone = prayer_data.get("meta", {}).get("timezone")
        if api_timezone and api_timezone != settings.timezone:
            logging.warning(
                "[PRAYER] Configured timezone %s differs from Aladhan timezone %s; "
                "using configured timezone",
                settings.timezone,
                api_timezone,
            )

        prayers = {}
        for name in PRAYER_NAMES:
            raw_time = prayer_data["timings"][name]
            clock_time = datetime.strptime(raw_time.split()[0], "%H:%M").time()
            prayer_dt = datetime.combine(
                mosque_date,
                clock_time,
                tzinfo=mosque_zone,
            )
            prayers[name] = prayer_dt.isoformat(timespec="seconds")

        return {
            "date": mosque_date.isoformat(),
            "timezone": settings.timezone,
            "prayers": prayers,
        }

    except Exception as e:
        logging.error(f"[PRAYER] Failed to fetch prayer times: {e}")
        return {}
