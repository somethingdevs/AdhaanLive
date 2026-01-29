from fastapi import APIRouter

from core.globals import detection_active_flag
from core.stream_refresher import read_cached_url
from core.detector import start_audio_detection, stop_audio_detection
from core.playback import PLAYBACK
from core.runtime_state import state

router = APIRouter()


# ---------- PLAYBACK ----------
@router.post("/control/playback/stop")
def stop_playback():
    PLAYBACK.stop()
    state.playback_active = False
    return {"success": True, "message": "Playback stopped"}


# ---------- DETECTION ----------
@router.post("/control/detection/start")
def start_detection():
    if detection_active_flag.is_set():
        return {"success": False, "message": "Detection already running"}

    url = read_cached_url()
    if not url:
        return {"success": False, "message": "No stream URL available"}

    start_audio_detection(url)
    detection_active_flag.set()
    state.detection_active = True

    return {"success": True, "message": "Detection started"}


@router.post("/control/detection/stop")
def stop_detection():
    if not detection_active_flag.is_set():
        return {"success": False, "message": "Detection not running"}

    stop_audio_detection()
    detection_active_flag.clear()
    state.detection_active = False

    return {"success": True, "message": "Detection stopped"}
