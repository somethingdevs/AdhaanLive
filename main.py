"""
Main entry point for the Adhaan Streamer project.

Usage:
    python main.py                → normal mode (uses livestream)
    python main.py --test         → test mode (plays local adhaan.mp3)

This script initializes logging, loads configuration,
and invokes the Adhaan streamer.
"""

import argparse
import logging
import sys
from core.streamer import start_streamer


def configure_logging(verbose: bool = False) -> None:
    """Configure global logging for the application."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="📢 Adhaan Streamer — Listen to live Adhaan automatically via livestream."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode — plays local adhaan.mp3 instead of using livestream.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging for troubleshooting.",
    )
    return parser.parse_args()


def main() -> None:
    """Main function that launches the Adhaan Streamer."""
    args = parse_args()
    configure_logging(verbose=args.verbose)

    try:
        start_streamer(test_mode=args.test)
    except KeyboardInterrupt:
        logging.info("🛑 Stopping Adhaan Streamer... Goodbye 👋")
        sys.exit(0)
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
