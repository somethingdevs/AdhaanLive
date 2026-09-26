"""Resolve public Click2Stream/Angelcam HLS URLs without a browser."""

import html
import logging
import re
import time
from typing import Optional
from urllib.parse import urlsplit

import requests

from utils.config_loader import load_config


REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
ANGELCAM_PLAYER_URL = "https://v.angelcam.com/iframe"

# These are public player configuration fields, not JavaScript to execute.
PLAYER_ID_PATTERN = re.compile(
    r"""new\s+Angelcam\.player\s*\(\s*['"][^'"]+['"]\s*,\s*\{\s*"""
    r"""(?:id|['"]id['"])\s*:\s*['"]([A-Za-z0-9_-]+)['"]""",
)
HLS_PATTERN = re.compile(
    r"""['"]hls['"]\s*:\s*(?P<quote>['"])(?P<url>.*?)(?P=quote)""",
    re.DOTALL,
)
JS_ESCAPE_PATTERN = re.compile(r"""\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[/\\'"])""")


def _decode_player_url(value: str) -> str:
    """Decode the escaped URL string emitted by the Angelcam player template."""
    def decode(match):
        escaped = match.group()[1:]
        if escaped[0] in ("u", "x"):
            return chr(int(escaped[1:], 16))
        return escaped

    return html.unescape(JS_ESCAPE_PATTERN.sub(decode, value))


def _is_hls_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme in ("http", "https")
        and bool(parsed.netloc)
        and parsed.path.lower().endswith(".m3u8")
        and "\\" not in value
        and not any(ord(character) < 32 for character in value)
    )


def _fetch_page(url: str, **kwargs) -> str:
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
    response.raise_for_status()
    return response.text


def get_m3u8_url(page_url: str) -> Optional[str]:
    """Resolve a public page, Angelcam iframe, or explicitly configured HLS URL.

    Public pages contain an Angelcam player ID. Its iframe response contains a
    fresh signed HLS URL; no browser, JavaScript execution, or account is needed.
    This is a provider-specific HTML integration, not a guaranteed public API.
    """
    try:
        if _is_hls_url(page_url):
            return page_url

        if urlsplit(page_url).scheme not in ("http", "https"):
            logging.warning("[STREAM] Livestream URL must use HTTP or HTTPS")
            return None

        page = _fetch_page(page_url)
        player = PLAYER_ID_PATTERN.search(page)
        if player:
            page = _fetch_page(ANGELCAM_PLAYER_URL, params={"v": player.group(1)})

        stream = HLS_PATTERN.search(page)
        if not stream:
            logging.warning("[STREAM] Public player has no HLS URL; offline or markup changed")
            return None

        stream_url = _decode_player_url(stream.group("url"))
        if not _is_hls_url(stream_url):
            logging.warning("[STREAM] Public player returned an invalid HLS URL")
            return None

        logging.info("[STREAM] HLS URL resolved over HTTP")
        return stream_url
    except (requests.RequestException, ValueError) as exc:
        # Request exception strings may contain signed stream tokens.
        logging.warning("[STREAM] URL resolution failed (%s)", type(exc).__name__)
        return None


def get_new_url_func() -> Optional[str]:
    """Re-resolve the configured source on each refresh to renew signed URLs."""
    livestream = load_config().get("livestream", {})
    page_url = livestream.get("url") if isinstance(livestream, dict) else None
    if not isinstance(page_url, str) or not page_url.strip():
        logging.error("[STREAM] Set livestream.url in config.yml")
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        url = get_m3u8_url(page_url.strip())
        if url:
            logging.info("[STREAM] New URL acquired (attempt %s)", attempt)
            return url

        logging.warning("[STREAM] Retry %s/%s failed", attempt, MAX_RETRIES)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    logging.error("[STREAM] All retries failed")
    return None
