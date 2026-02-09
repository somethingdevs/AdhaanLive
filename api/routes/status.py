from fastapi import APIRouter
from core.runtime_state import state
from core.stream_refresher import get_current_stream_url


router = APIRouter()

@router.get("/status")
def status():
    return {
        "detection_active": state.detection_active,
        "playback_active": state.playback_active,
        "adhaan_active": state.adhaan_active,
        "last_event": state.last_event,
        "last_event_time": state.last_event_time,
        "stream_url": get_current_stream_url()
    }
