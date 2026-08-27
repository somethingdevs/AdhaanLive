from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from core.prayer_scheduler import (
    get_next_prayer,
    get_prayer_window,
    seconds_until_mosque_midnight,
)


SUMMER_SCHEDULE = {
    "date": "2026-08-27",
    "timezone": "America/Chicago",
    "prayers": {
        "Fajr": "2026-08-27T05:30:00-05:00",
        "Dhuhr": "2026-08-27T13:30:00-05:00",
        "Asr": "2026-08-27T17:00:00-05:00",
        "Maghrib": "2026-08-27T20:00:00-05:00",
        "Isha": "2026-08-27T21:15:00-05:00",
    },
}


def test_dallas_schedule_selects_same_prayer_from_atlanta_and_utc():
    atlanta_now = datetime(
        2026,
        8,
        27,
        14,
        29,
        tzinfo=ZoneInfo("America/New_York"),
    )
    utc_now = datetime(2026, 8, 27, 18, 29, tzinfo=timezone.utc)

    atlanta_result = get_next_prayer(SUMMER_SCHEDULE, now=atlanta_now)
    utc_result = get_next_prayer(SUMMER_SCHEDULE, now=utc_now)

    assert atlanta_now == utc_now
    assert atlanta_result == utc_result
    assert atlanta_result == (
        "Dhuhr",
        datetime.fromisoformat("2026-08-27T13:30:00-05:00"),
    )


def test_scheduler_moves_past_dallas_prayer_at_same_absolute_instant():
    after_dhuhr_in_atlanta = datetime(
        2026,
        8,
        27,
        14,
        31,
        tzinfo=ZoneInfo("America/New_York"),
    )

    name, prayer_dt = get_next_prayer(
        SUMMER_SCHEDULE,
        now=after_dhuhr_in_atlanta,
    )

    assert name == "Asr"
    assert prayer_dt == datetime.fromisoformat("2026-08-27T17:00:00-05:00")


def test_dallas_and_atlanta_winter_offsets_are_handled_automatically():
    winter_schedule = {
        "date": "2026-01-15",
        "timezone": "America/Chicago",
        "prayers": {
            "Dhuhr": "2026-01-15T13:30:00-06:00",
        },
    }
    atlanta_now = datetime(
        2026,
        1,
        15,
        14,
        29,
        tzinfo=ZoneInfo("America/New_York"),
    )

    name, prayer_dt = get_next_prayer(winter_schedule, now=atlanta_now)

    assert name == "Dhuhr"
    assert prayer_dt.astimezone(timezone.utc) == datetime(
        2026,
        1,
        15,
        19,
        30,
        tzinfo=timezone.utc,
    )


def test_get_next_prayer_ignores_malformed_and_naive_entries():
    schedule = {
        "prayers": {
            "Broken": "not-a-time",
            "Naive": "2026-08-27T15:00:00",
            "Asr": "2026-08-27T17:00:00-05:00",
        }
    }
    now = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)

    name, prayer_dt = get_next_prayer(schedule, now=now)

    assert name == "Asr"
    assert prayer_dt == datetime.fromisoformat("2026-08-27T17:00:00-05:00")


def test_get_next_prayer_waits_for_refresh_after_last_prayer():
    now = datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)

    assert get_next_prayer(SUMMER_SCHEDULE, now=now) == (None, None)


def test_prayer_window_preserves_timezone_and_offsets():
    prayer_dt = datetime.fromisoformat("2026-08-27T13:30:00-05:00")

    wake_dt, timeout_dt = get_prayer_window(prayer_dt)

    assert wake_dt == prayer_dt - timedelta(minutes=10)
    assert timeout_dt == prayer_dt + timedelta(minutes=90)
    assert wake_dt.utcoffset() == timedelta(hours=-5)


def test_refresh_rollover_uses_dallas_midnight_not_atlanta_or_utc_midnight():
    # Atlanta has crossed midnight, but Dallas still has 30 minutes left.
    atlanta_now = datetime(
        2026,
        8,
        28,
        0,
        30,
        tzinfo=ZoneInfo("America/New_York"),
    )

    seconds = seconds_until_mosque_midnight(
        "America/Chicago",
        now=atlanta_now,
    )

    assert seconds == 30 * 60


def test_scheduler_rejects_naive_now_value():
    naive_now = datetime(2026, 8, 27, 12, 0)

    try:
        get_next_prayer(SUMMER_SCHEDULE, now=naive_now)
    except ValueError as exc:
        assert str(exc) == "now must be timezone-aware"
    else:
        raise AssertionError("Expected a timezone validation error")
