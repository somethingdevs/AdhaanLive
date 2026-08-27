from datetime import datetime, timezone
from types import SimpleNamespace

from utils.config_loader import PrayerSettings
from utils.prayer_api import get_prayer_times


SETTINGS = PrayerSettings(
    city="Dallas",
    country="US",
    timezone="America/Chicago",
    method=2,
    school=1,
)


def aladhan_payload(timezone_name="America/Chicago"):
    return {
        "data": {
            "timings": {
                "Fajr": "05:30",
                "Dhuhr": "13:30",
                "Asr": "17:00",
                "Maghrib": "20:00",
                "Isha": "21:15",
            },
            "meta": {"timezone": timezone_name},
        }
    }


def test_request_uses_configured_city_country_method_school_and_dallas_date(
    monkeypatch,
):
    request = {}

    def fake_get(url, params, timeout):
        request.update(url=url, params=params, timeout=timeout)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: aladhan_payload(),
        )

    monkeypatch.setattr("utils.prayer_api.requests.get", fake_get)
    # At this instant Atlanta is on Aug 28, but Dallas is still on Aug 27.
    now = datetime(2026, 8, 28, 4, 30, tzinfo=timezone.utc)

    schedule = get_prayer_times(SETTINGS, now=now)

    assert request == {
        "url": "https://api.aladhan.com/v1/timingsByCity/27-08-2026",
        "params": {
            "city": "Dallas",
            "country": "US",
            "method": 2,
            "school": 1,
        },
        "timeout": 10,
    }
    assert schedule["date"] == "2026-08-27"
    assert schedule["timezone"] == "America/Chicago"
    assert schedule["prayers"]["Dhuhr"] == "2026-08-27T13:30:00-05:00"


def test_config_timezone_wins_and_api_mismatch_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(
        "utils.prayer_api.requests.get",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: aladhan_payload("America/New_York"),
        ),
    )

    schedule = get_prayer_times(
        SETTINGS,
        now=datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc),
    )

    assert schedule["prayers"]["Dhuhr"] == "2026-01-15T13:30:00-06:00"
    assert "differs from Aladhan timezone" in caplog.text


def test_api_failure_returns_empty_schedule(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr("utils.prayer_api.requests.get", fail)

    assert get_prayer_times(SETTINGS) == {}
