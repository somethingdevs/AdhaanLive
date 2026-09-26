"""Offline coverage for the public player integration; no browser or network."""

from types import SimpleNamespace

import pytest
import requests

from utils import livestream


PUBLIC_PAGE = """<script>
new Angelcam.player('player_liveview', {
  id: "test-camera",
  autoplay: true
});
</script>"""
PLAYER_PAGE = r"""<script>player.load({
  'hls': 'https://edge.example.test/live.m3u8?token=example\u002Dtoken\u003D'
});</script>"""


def stub_pages(monkeypatch, pages):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        page = pages[len(calls) - 1]
        if isinstance(page, Exception):
            raise page
        return SimpleNamespace(text=page, raise_for_status=lambda: None)

    monkeypatch.setattr(livestream.requests, "get", get)
    return calls


def test_public_page_resolves_player_and_decodes_signed_url(monkeypatch):
    calls = stub_pages(monkeypatch, [PUBLIC_PAGE, PLAYER_PAGE])

    result = livestream.get_m3u8_url("https://masjid.example.test/")

    assert result == "https://edge.example.test/live.m3u8?token=example-token="
    assert calls == [
        ("https://masjid.example.test/", {"timeout": 20}),
        (livestream.ANGELCAM_PLAYER_URL, {"timeout": 20, "params": {"v": "test-camera"}}),
    ]


def test_iframe_url_resolves_without_a_public_page(monkeypatch):
    calls = stub_pages(monkeypatch, [PLAYER_PAGE])

    assert livestream.get_m3u8_url("https://v.angelcam.com/iframe?v=test-camera")
    assert len(calls) == 1


def test_explicit_hls_url_preserves_query_without_discovery(monkeypatch):
    calls = stub_pages(monkeypatch, [])
    url = "https://edge.example.test/live.m3u8?token=already%2Bencoded"

    assert livestream.get_m3u8_url(url) == url
    assert calls == []


def test_html_entities_and_javascript_slash_escapes(monkeypatch):
    page = r'''player.load({"hls": "https:\/\/edge.example.test/live.m3u8?a=1&amp;b=2"});'''
    stub_pages(monkeypatch, [page])

    assert livestream.get_m3u8_url("https://v.angelcam.com/iframe?v=test") == (
        "https://edge.example.test/live.m3u8?a=1&b=2"
    )


@pytest.mark.parametrize("page", [
    "<html>Camera offline</html>",
    "player.load({'hls': 'javascript:alert(1)'});",
    "player.load({'hls': 'https://example.test/not-a-playlist'});",
])
def test_missing_or_invalid_stream_fails_without_guessing(monkeypatch, page):
    stub_pages(monkeypatch, [page])
    assert livestream.get_m3u8_url("https://v.angelcam.com/iframe?v=test") is None


def test_http_failure_does_not_leak_url_tokens(monkeypatch, caplog):
    stub_pages(monkeypatch, [requests.HTTPError("https://example.test/?token=secret")])

    assert livestream.get_m3u8_url("https://masjid.example.test/") is None
    assert "HTTPError" in caplog.text
    assert "secret" not in caplog.text


def test_timeout_on_iframe_returns_none(monkeypatch):
    stub_pages(monkeypatch, [PUBLIC_PAGE, requests.Timeout()])
    assert livestream.get_m3u8_url("https://masjid.example.test/") is None


def test_non_http_source_is_rejected_without_fetching(monkeypatch):
    calls = stub_pages(monkeypatch, [])
    assert livestream.get_m3u8_url("file:///tmp/live.m3u8") is None
    assert calls == []


def test_refresh_fetches_new_player_configuration_each_time(monkeypatch):
    monkeypatch.setattr(
        livestream, "load_config", lambda: {"livestream": {"url": "https://masjid.example.test/"}}
    )
    stub_pages(monkeypatch, [PUBLIC_PAGE, PLAYER_PAGE, PUBLIC_PAGE,
                             PLAYER_PAGE.replace("example", "renewed")])

    first = livestream.get_new_url_func()
    second = livestream.get_new_url_func()

    assert "example-token=" in first
    assert "renewed-token=" in second


def test_retry_recovers_from_transient_failure(monkeypatch):
    monkeypatch.setattr(
        livestream, "load_config", lambda: {"livestream": {"url": "https://masjid.example.test/"}}
    )
    calls = stub_pages(monkeypatch, [requests.Timeout(), PUBLIC_PAGE, PLAYER_PAGE])
    sleeps = []
    monkeypatch.setattr(livestream.time, "sleep", sleeps.append)

    assert livestream.get_new_url_func()
    assert len(calls) == 3
    assert sleeps == [2]


def test_retries_are_bounded(monkeypatch):
    monkeypatch.setattr(
        livestream, "load_config", lambda: {"livestream": {"url": "https://masjid.example.test/"}}
    )
    calls = stub_pages(monkeypatch, [requests.Timeout()] * 3)
    sleeps = []
    monkeypatch.setattr(livestream.time, "sleep", sleeps.append)

    assert livestream.get_new_url_func() is None
    assert len(calls) == 3
    assert sleeps == [2, 2]


@pytest.mark.parametrize("config", [{}, {"livestream": None}, {"livestream": {"url": " "}}])
def test_missing_source_does_not_fall_back_to_another_masjid(monkeypatch, config):
    monkeypatch.setattr(livestream, "load_config", lambda: config)
    calls = stub_pages(monkeypatch, [])

    assert livestream.get_new_url_func() is None
    assert calls == []
