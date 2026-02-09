import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = os.path.join("assets", "logs")
SERVER_LOG_PATH = os.path.join(LOG_DIR, "adhaanlive.log")
CLIENT_LOG_PATH = os.path.join(LOG_DIR, "client.log")

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    # SERVER LOGGER
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    # File handler (server)
    server_file = TimedRotatingFileHandler(
        SERVER_LOG_PATH,
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    server_file.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))

    # Console handler (server only)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))

    root.addHandler(server_file)
    root.addHandler(console)

    # CLIENT LOGGER (file only)
    client_logger = logging.getLogger("adhaanlive.client")
    client_logger.setLevel(logging.INFO)
    client_logger.propagate = False

    client_file = TimedRotatingFileHandler(
        CLIENT_LOG_PATH,
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    client_file.setFormatter(logging.Formatter(
        "%(asctime)s | %(message)s"
    ))

    client_logger.addHandler(client_file)

    logging.info("[LOG] Logging initialized")
