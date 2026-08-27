from core.runtime_state import RuntimeState


def test_runtime_state_full_lifecycle():
    state = RuntimeState()

    state.start_detection("Fajr")
    assert state.detection_active is True
    assert state.current_prayer == "Fajr"
    assert state.started_at is not None
    assert state.last_event == "DETECTION_STARTED"

    state.start_adhaan()
    assert state.adhaan_active is True
    assert state.last_event == "ADHAAN_STARTED"

    state.end_adhaan()
    assert state.adhaan_active is False
    assert state.ended_at is not None
    assert state.last_event == "ADHAAN_ENDED"

    state.stop_detection()
    assert state.detection_active is False
    assert state.last_event == "DETECTION_STOPPED"


def test_reset_cycle_clears_transient_state():
    state = RuntimeState()
    state.start_detection("Maghrib")
    state.start_adhaan()
    state.end_adhaan()

    state.reset_cycle()

    assert state.detection_active is False
    assert state.adhaan_active is False
    assert state.current_prayer is None
    assert state.started_at is None
    assert state.ended_at is None
    assert state.last_event == "CYCLE_RESET"


def test_snapshot_is_serializable_and_complete():
    state = RuntimeState()
    state.start_detection("Asr")

    snapshot = state.snapshot()

    assert snapshot["detection_active"] is True
    assert snapshot["adhaan_active"] is False
    assert snapshot["current_prayer"] == "Asr"
    assert snapshot["last_event"] == "DETECTION_STARTED"
    assert isinstance(snapshot["last_event_time"], str)
    assert isinstance(snapshot["started_at"], str)
    assert snapshot["ended_at"] is None
    assert "playback_active" not in snapshot


def test_shutdown_records_request_without_inventing_playback_state():
    state = RuntimeState()

    state.shutdown()

    assert state.shutdown_requested is True
    assert state.last_event == "SYSTEM_SHUTDOWN"
    assert not hasattr(state, "playback_active")
