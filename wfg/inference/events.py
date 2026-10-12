"""Turns a stream of per-window class probabilities into fall alerts.

A single "fall" prediction is not enough to wake a relative at night. The
detector requires the fall class to win several consecutive windows, then
waits: if the person walks again they have got up (``recovered``); if they
stay down for ``inactivity_seconds`` an ``alert`` is raised. This
two-stage check is the main defence against false alarms from sitting or
lying down quickly.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

MONITORING, SUSPECTED, ALERT = "monitoring", "fall_suspected", "alert"


@dataclass
class DetectorConfig:
    fall_threshold: float = 0.4
    confirm_windows: int = 2
    inactivity_seconds: float = 20.0
    recovery_threshold: float = 0.6
    recovery_windows: int = 3
    smoothing: int = 3


@dataclass
class FallDetector:
    classes: list[str]
    cfg: DetectorConfig = field(default_factory=DetectorConfig)
    state: str = MONITORING
    suspected_at: float | None = None
    fall_prob: float = 0.0
    _fall_streak: int = 0
    _walk_streak: int = 0
    _history: deque = field(default_factory=lambda: deque(maxlen=8))

    def __post_init__(self):
        self.fall_id = self.classes.index("fall")
        self.walk_id = self.classes.index("walk")

    def activity(self) -> str:
        """Smoothed current activity (majority over the last few windows)."""
        if not self._history:
            return "unknown"
        recent = list(self._history)[-self.cfg.smoothing:]
        return self.classes[int(np.argmax(np.mean(recent, axis=0)))]

    def update(self, probs: np.ndarray, t: float) -> list[dict]:
        """Feed one window's probabilities at time ``t`` (seconds); returns emitted events."""
        probs = np.asarray(probs, dtype=float)
        self._history.append(probs)
        p_fall, p_walk = float(probs[self.fall_id]), float(probs[self.walk_id])
        events: list[dict] = []

        self._fall_streak = self._fall_streak + 1 if p_fall >= self.cfg.fall_threshold else 0
        self._walk_streak = self._walk_streak + 1 if p_walk >= self.cfg.recovery_threshold else 0

        if self.state == MONITORING:
            if self._fall_streak >= self.cfg.confirm_windows:
                self.state, self.suspected_at, self.fall_prob = SUSPECTED, t, p_fall
                self._walk_streak = 0
                events.append({"type": "fall_suspected", "t": t, "prob": p_fall})
        elif self.state == SUSPECTED:
            self.fall_prob = max(self.fall_prob, p_fall)
            if self._walk_streak >= self.cfg.recovery_windows:
                events.append({"type": "recovered", "t": t, "prob": self.fall_prob,
                               "after_s": round(t - self.suspected_at, 1)})
                self._reset()
            elif t - self.suspected_at >= self.cfg.inactivity_seconds:
                self.state = ALERT
                events.append({"type": "alert", "t": t, "prob": self.fall_prob,
                               "after_s": round(t - self.suspected_at, 1)})
        elif self.state == ALERT:
            if self._walk_streak >= self.cfg.recovery_windows:
                events.append({"type": "recovered", "t": t, "prob": self.fall_prob,
                               "after_s": round(t - self.suspected_at, 1)})
                self._reset()
        return events

    def acknowledge(self, t: float) -> list[dict]:
        if self.state == MONITORING:
            return []
        self._reset()
        return [{"type": "acknowledged", "t": t, "prob": 0.0}]

    def _reset(self):
        self.state, self.suspected_at, self.fall_prob = MONITORING, None, 0.0
        self._fall_streak = self._walk_streak = 0
