import yaml
import logging
from pathlib import Path


def load_config(config_path: str = "config.yml") -> dict:
    """Load YAML configuration file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found at {config_file.resolve()}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
