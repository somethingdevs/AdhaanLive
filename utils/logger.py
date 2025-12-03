# utils/logger.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = os.path.join("assets", "logs")
LOG_PATH = os.path.join(LOG_DIR, "adhaanlive.log")

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clean old handlers (avoid duplicates when main.py reloads)
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- FILE HANDLER (rotates daily, keeps 14 days) ---
    file_handler = TimedRotatingFileHandler(
        LOG_PATH,
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))

    # --- CONSOLE HANDLER (minimal logs) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info("[LOG] Logging initialized → assets/logs/adhaanlive.log")
