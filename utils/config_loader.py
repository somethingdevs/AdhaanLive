from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


@dataclass(frozen=True)
class PrayerSettings:
    """Validated prayer configuration used by the API and scheduler."""

    city: str
    country: str
    timezone: str
    method: int
    school: int


def load_config(config_path: str = "config.yml") -> dict:
    """Load YAML configuration file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found at {config_file.resolve()}")
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("Config file must contain a YAML mapping")
    return config


def load_prayer_settings(config_path: str = "config.yml") -> PrayerSettings:
    """Load and validate the prayer settings from config.yml."""
    config = load_config(config_path)
    settings = config.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("Config must contain a 'settings' mapping")

    city = _required_text(settings, "city")
    country = _required_text(settings, "country")
    timezone_name = _required_text(settings, "timezone")
    method = _required_integer(settings, "method")
    school = _required_integer(settings, "school")

    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Invalid settings.timezone '{timezone_name}'; use an IANA name "
            "such as 'America/Chicago'"
        ) from exc

    if school not in (0, 1):
        raise ValueError("settings.school must be 0 (Shafi) or 1 (Hanafi)")

    if method < 0:
        raise ValueError("settings.method must be a non-negative integer")

    return PrayerSettings(
        city=city,
        country=country,
        timezone=timezone_name,
        method=method,
        school=school,
    )


def _required_text(settings: dict, key: str) -> str:
    value = settings.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"settings.{key} must be a non-empty string")
    return value.strip()


def _required_integer(settings: dict, key: str) -> int:
    value = settings.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"settings.{key} must be an integer")
    return value
