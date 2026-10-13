"""Real-time loop: every ``hop`` seconds take the latest window, classify it, update the detector."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np

from wfg.collector.hub import CSIHub
from wfg.dsp.features import relative_amplitude
from wfg.inference.events import DetectorConfig, FallDetector
from wfg.inference.predictor import Predictor

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, hub: CSIHub, predictor: Predictor, hop: float = 0.5,
                 detector_cfg: DetectorConfig | None = None,
                 on_update: Callable[[dict], None] | None = None,
                 on_event: Callable[[dict], None] | None = None):
        self.hub, self.predictor, self.hop = hub, predictor, hop
        self.detector = FallDetector(predictor.classes, detector_cfg or DetectorConfig())
        self.on_update, self.on_event = on_update, on_event
        self.latest: dict = {"state": "starting", "activity": "unknown", "probs": {}, "motion": 0.0, "t": 0.0}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> "Engine":
        self._thread = threading.Thread(target=self._run, name="inference", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def step(self, now: float | None = None) -> dict | None:
        """One inference step; public so tests and offline replays can drive it directly."""
        win = self.hub.window(self.predictor.window_seconds, partial=True)  # survives a dead board
        if win is None:
            with self._lock:
                self.latest = {**self.latest, "state": "waiting_for_nodes"}
            return None
        now = time.time() if now is None else now
        t0 = time.perf_counter()
        probs = self.predictor.predict(win)
        latency_ms = (time.perf_counter() - t0) * 1000
        tail = win[:, -int(self.hub.fs):]  # last second
        motion = float(np.abs(relative_amplitude(tail, self.hub.fs)).mean())
        with self._lock:
            events = self.detector.update(probs, now)
            self.latest = {
                "t": now,
                "state": self.detector.state,
                "activity": self.detector.activity(),
                "probs": {c: round(float(p), 4) for c, p in zip(self.predictor.classes, probs)},
                "motion": round(motion, 5),
                "latency_ms": round(latency_ms, 1),
            }
        if self.on_update:
            self.on_update(self.latest)
        for ev in events:
            log.info("event %s", ev)
            if self.on_event:
                self.on_event(ev)
        return self.latest

    def acknowledge(self) -> list[dict]:
        with self._lock:
            events = self.detector.acknowledge(time.time())
        for ev in events:
            if self.on_event:
                self.on_event(ev)
        return events

    def _run(self) -> None:
        next_t = time.time()
        while not self._stop.is_set():
            try:
                self.step()
            except Exception:  # keep the guard running even if one window is malformed
                log.exception("inference step failed")
            next_t += self.hop
            time.sleep(max(0.0, next_t - time.time()))
