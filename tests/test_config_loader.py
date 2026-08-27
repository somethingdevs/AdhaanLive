import pytest

from utils.config_loader import load_prayer_settings


def write_config(tmp_path, settings):
    path = tmp_path / "config.yml"
    lines = ["settings:"]
    for key, value in settings.items():
        rendered = f'"{value}"' if isinstance(value, str) else str(value)
        lines.append(f"  {key}: {rendered}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def valid_settings():
    return {
        "city": "Dallas",
        "country": "US",
        "timezone": "America/Chicago",
        "method": 2,
        "school": 1,
    }


def test_load_prayer_settings_reads_all_yaml_options(tmp_path):
    path = write_config(tmp_path, valid_settings())

    settings = load_prayer_settings(path)

    assert settings.city == "Dallas"
    assert settings.country == "US"
    assert settings.timezone == "America/Chicago"
    assert settings.method == 2
    assert settings.school == 1


@pytest.mark.parametrize("timezone_name", ["", "CST", "Mars/Olympus_Mons"])
def test_invalid_timezone_fails_clearly(tmp_path, timezone_name):
    config = valid_settings()
    config["timezone"] = timezone_name
    path = write_config(tmp_path, config)

    with pytest.raises(ValueError, match="settings.timezone"):
        load_prayer_settings(path)


@pytest.mark.parametrize("school", [-1, 2, "1"])
def test_invalid_school_fails_clearly(tmp_path, school):
    config = valid_settings()
    config["school"] = school
    path = write_config(tmp_path, config)

    with pytest.raises(ValueError, match="settings.school"):
        load_prayer_settings(path)


def test_missing_required_setting_fails_clearly(tmp_path):
    config = valid_settings()
    del config["city"]
    path = write_config(tmp_path, config)

    with pytest.raises(ValueError, match="settings.city"):
        load_prayer_settings(path)
