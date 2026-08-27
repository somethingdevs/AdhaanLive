from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.app import app
from api.routes import control as control_routes
from api.routes import schedule as schedule_routes
from api.routes import status as status_routes


client = TestClient(app)


def test_health_response():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_response_is_detection_only(monkeypatch):
    fake_state = SimpleNamespace(
        detection_active=True,
        adhaan_active=False,
        last_event="DETECTION_STARTED",
        last_event_time=None,
    )
    monkeypatch.setattr(status_routes, "state", fake_state)
    monkeypatch.setattr(
        status_routes,
        "get_current_stream_url",
        lambda: "https://example.test/live.m3u8",
    )

    response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {
        "detection_active": True,
        "adhaan_active": False,
        "last_event": "DETECTION_STARTED",
        "last_event_time": None,
        "stream_url": "https://example.test/live.m3u8",
    }
    assert "playback_active" not in response.json()


def test_schedule_response_when_not_loaded(monkeypatch, tmp_path):
    monkeypatch.setattr(schedule_routes, "FILE", tmp_path / "missing.json")

    response = client.get("/schedule")

    assert response.status_code == 200
    assert response.json() == {"error": "schedule not loaded"}


def test_start_detection_success(monkeypatch):
    started_with = []
    monkeypatch.setattr(
        control_routes,
        "state",
        SimpleNamespace(detection_active=False),
    )
    monkeypatch.setattr(
        control_routes,
        "get_current_stream_url",
        lambda: "https://example.test/live.m3u8",
    )
    monkeypatch.setattr(
        control_routes,
        "start_audio_detection",
        started_with.append,
    )

    response = client.post("/control/detection/start")

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Detection started"}
    assert started_with == ["https://example.test/live.m3u8"]


def test_start_detection_requires_stream_url(monkeypatch):
    monkeypatch.setattr(
        control_routes,
        "state",
        SimpleNamespace(detection_active=False),
    )
    monkeypatch.setattr(control_routes, "get_current_stream_url", lambda: None)

    response = client.post("/control/detection/start")

    assert response.json() == {
        "success": False,
        "message": "No stream URL available",
    }


def test_start_detection_rejects_duplicate_start(monkeypatch):
    monkeypatch.setattr(
        control_routes,
        "state",
        SimpleNamespace(detection_active=True),
    )

    response = client.post("/control/detection/start")

    assert response.json() == {
        "success": False,
        "message": "Detection already running",
    }


def test_stop_detection_success(monkeypatch):
    stopped = []
    monkeypatch.setattr(
        control_routes,
        "state",
        SimpleNamespace(detection_active=True),
    )
    monkeypatch.setattr(
        control_routes,
        "stop_audio_detection",
        lambda: stopped.append(True),
    )

    response = client.post("/control/detection/stop")

    assert response.json() == {"success": True, "message": "Detection stopped"}
    assert stopped == [True]


def test_stop_detection_rejects_duplicate_stop(monkeypatch):
    monkeypatch.setattr(
        control_routes,
        "state",
        SimpleNamespace(detection_active=False),
    )

    response = client.post("/control/detection/stop")

    assert response.json() == {
        "success": False,
        "message": "Detection not running",
    }


def test_server_playback_route_is_removed():
    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }

    assert "/control/playback/stop" not in paths
