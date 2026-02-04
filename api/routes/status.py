from fastapi import APIRouter
from core.globals import detection_active_flag
from core.playback import PLAYBACK
from core.runtime_state import state
from core.stream_refresher import read_cached_url

router = APIRouter()

@router.get("/status")
def status():
    return {
        "detection_active": detection_active_flag.is_set(),
        "playback_active": PLAYBACK.is_alive(),
        "adhaan_active": state.adhaan_active,
        "last_event": state.last_event,
        "last_event_time": state.last_event_time,
        "stream_url": read_cached_url(),
    }
