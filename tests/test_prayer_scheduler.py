from datetime import datetime, timedelta

from core.prayer_scheduler import get_next_prayer, get_prayer_window


PRAYERS = {
    "Fajr": "05:30:00",
    "Dhuhr": "12:30:00",
    "Asr": "16:15:00",
    "Maghrib": "19:45:00",
    "Isha": "21:00:00",
}


def test_get_next_prayer_selects_first_upcoming_prayer():
    now = datetime(2026, 8, 27, 11, 0)

    name, prayer_dt = get_next_prayer(PRAYERS, now=now)

    assert name == "Dhuhr"
    assert prayer_dt == datetime(2026, 8, 27, 12, 30)


def test_get_next_prayer_rolls_over_to_tomorrows_fajr():
    now = datetime(2026, 8, 27, 22, 0)

    name, prayer_dt = get_next_prayer(PRAYERS, now=now)

    assert name == "Fajr"
    assert prayer_dt == datetime(2026, 8, 28, 5, 30)


def test_get_next_prayer_ignores_malformed_entries():
    prayers = {"Broken": "not-a-time", "Asr": "16:15:00"}
    now = datetime(2026, 8, 27, 15, 0)

    name, prayer_dt = get_next_prayer(prayers, now=now)

    assert name == "Asr"
    assert prayer_dt == datetime(2026, 8, 27, 16, 15)


def test_get_next_prayer_has_safe_fallback_without_fajr():
    now = datetime(2026, 8, 27, 22, 0)

    name, prayer_dt = get_next_prayer({}, now=now)

    assert name == "Unknown"
    assert prayer_dt == now + timedelta(hours=6)


def test_prayer_window_uses_configured_wake_and_timeout_offsets():
    prayer_dt = datetime(2026, 8, 27, 12, 30)

    wake_dt, timeout_dt = get_prayer_window(prayer_dt)

    assert wake_dt == datetime(2026, 8, 27, 12, 20)
    assert timeout_dt == datetime(2026, 8, 27, 14, 0)
