from threading import Lock
from datetime import datetime
from typing import Optional, Dict


class RuntimeState:
    """
    Single source of truth for the entire application runtime.
    All core modules WRITE here.
    API layer READS here.
    """

    def __init__(self):
        self.lock = Lock()

        # Core lifecycle flags
        self.detection_active: bool = False
        self.adhaan_active: bool = False

        # Context
        self.current_prayer: Optional[str] = None

        # Event metadata
        self.last_event: Optional[str] = None
        self.last_event_time: Optional[datetime] = None

        # Optional timing
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None

        self.shutdown_requested = False

    # Internal helpers
    def _set_event(self, event: str):
        self.last_event = event
        self.last_event_time = datetime.utcnow()

    # State transitions
    def start_detection(self, prayer: Optional[str] = None):
        with self.lock:
            self.detection_active = True
            self.current_prayer = prayer
            self.started_at = datetime.utcnow()
            self._set_event("DETECTION_STARTED")

    def stop_detection(self):
        with self.lock:
            self.detection_active = False
            self._set_event("DETECTION_STOPPED")

    def start_adhaan(self):
        with self.lock:
            self.adhaan_active = True
            self._set_event("ADHAAN_STARTED")

    def end_adhaan(self):
        with self.lock:
            self.adhaan_active = False
            self.ended_at = datetime.utcnow()
            self._set_event("ADHAAN_ENDED")

    def reset_cycle(self):
        """
        Called when a prayer cycle fully completes.
        """
        with self.lock:
            self.detection_active = False
            self.adhaan_active = False
            self.current_prayer = None
            self.started_at = None
            self.ended_at = None
            self._set_event("CYCLE_RESET")

    # Read-only snapshot
    def snapshot(self) -> Dict:
        """
        Safe, consistent view for API / SSE / logging.
        """
        with self.lock:
            return {
                "detection_active": self.detection_active,
                "adhaan_active": self.adhaan_active,
                "current_prayer": self.current_prayer,
                "last_event": self.last_event,
                "last_event_time": (
                    self.last_event_time.isoformat()
                    if self.last_event_time
                    else None
                ),
                "started_at": (
                    self.started_at.isoformat()
                    if self.started_at
                    else None
                ),
                "ended_at": (
                    self.ended_at.isoformat()
                    if self.ended_at
                    else None
                ),
            }

    def shutdown(self):
        with self.lock:
            self.shutdown_requested = True
            self._set_event("SYSTEM_SHUTDOWN")

# Singleton instance (import everywhere)
state = RuntimeState()
