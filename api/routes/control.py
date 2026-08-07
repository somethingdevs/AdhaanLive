# =====================================
# control.py — STATE-SAFE
# =====================================

from fastapi import APIRouter

from core.detector import start_audio_detection, stop_audio_detection
from core.runtime_state import state
from core.stream_refresher import get_current_stream_url

router = APIRouter()


# ---------- DETECTION ----------

@router.post("/control/detection/start")
def start_detection():
    """
    Manually start adhaan detection.
    """
    if state.detection_active:
        return {"success": False, "message": "Detection already running"}

    stream_url = get_current_stream_url()
    if not stream_url:
        return {"success": False, "message": "No stream URL available"}

    start_audio_detection(stream_url)

    return {"success": True, "message": "Detection started"}


@router.post("/control/detection/stop")
def stop_detection():
    """
    Manually stop adhaan detection.
    """
    if not state.detection_active:
        return {"success": False, "message": "Detection not running"}

    stop_audio_detection()

    return {"success": True, "message": "Detection stopped"}
