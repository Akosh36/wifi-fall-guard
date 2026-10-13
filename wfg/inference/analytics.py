"""Extra per-window outputs on top of the activity classifier: position and vital signs."""

from __future__ import annotations

import threading
import time

from wfg.collector.hub import CSIHub
from wfg.geometry import RoomLayout
from wfg.inference.localize import LinkLocalizer
from wfg.inference.vitals import VitalsConfig, estimate_vitals

RESTING = {"still", "sit", "lie"}


class Analytics:
    """Called after every engine step; adds ``location`` and ``vitals`` to the status.

    Vital signs are only estimated after the person has rested for
    ``rest_seconds`` (walking swamps the chest motion) and at most every
    ``vitals_every`` seconds, in a background thread because a 30 s window
    takes a moment to process.
    """

    def __init__(self, hub: CSIHub, layout: RoomLayout, rest_seconds: float = 20.0, vitals_every: float = 5.0,
                 vitals_cfg: VitalsConfig | None = None):
        self.hub, self.layout = hub, layout
        self.localizer = LinkLocalizer(layout, hub.fs)
        self.vitals_cfg = vitals_cfg or VitalsConfig()
        self.rest_seconds, self.vitals_every = rest_seconds, vitals_every
        self.location: dict | None = None
        self.vitals: dict = {"breath_bpm": None, "heart_bpm": None, "breath_q": 0.0, "heart_q": 0.0, "t": None}
        self._rest_since: float | None = None
        self._last_vitals = 0.0
        self._busy = threading.Lock()

    def update(self, activity: str, state: str, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        present = activity not in ("empty", "unknown")
        win = self.hub.window(1.0)
        if win is not None:
            self.location = self.localizer.update(win, present)

        resting = activity in RESTING or state in ("fall_suspected", "alert")
        if not (present and resting):
            self._rest_since = None
            self.vitals = {**self.vitals, "breath_bpm": None, "heart_bpm": None}
        else:
            self._rest_since = self._rest_since or now
            if (now - self._rest_since >= self.rest_seconds and now - self._last_vitals >= self.vitals_every
                    and self._busy.acquire(blocking=False)):
                self._last_vitals = now
                seconds = min(self.vitals_cfg.window_seconds, now - self._rest_since)
                threading.Thread(target=self._vitals, args=(seconds, now), daemon=True).start()
        return {"location": self.location, "vitals": self.vitals}

    def _vitals(self, seconds: float, now: float) -> None:
        try:
            win = self.hub.window(seconds)
            if win is not None:
                self.vitals = {**estimate_vitals(win, self.hub.fs, self.vitals_cfg), "t": now}
        finally:
            self._busy.release()
