from threading import Lock

class RuntimeState:
    def __init__(self):
        self.lock = Lock()
        self.adhaan_active = False
        self.playback_active = False
        self.detection_active = False
        self.last_event = None
        self.last_event_time = None

state = RuntimeState()
