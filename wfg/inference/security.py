"""Home security mode: when the owner is away, any presence in the room is an intrusion.

States: ``off`` -> (arm) -> ``arming`` (exit delay, so the owner can leave)
-> ``armed`` -> presence for ``confirm_windows`` windows -> ``intrusion``.
``intrusion`` returns to ``armed`` after ``quiet_seconds`` of an empty room
(and fires again if someone appears later). Disarming returns to ``off``.
"""

from __future__ import annotations

from dataclasses import dataclass

OFF, ARMING, ARMED, INTRUSION = "off", "arming", "armed", "intrusion"


@dataclass
class SecurityConfig:
    exit_delay: float = 30.0       # seconds after arming before motion counts
    confirm_windows: int = 3       # consecutive non-empty windows (0.5 s hop -> 1.5 s)
    quiet_seconds: float = 60.0    # empty room this long ends an intrusion


class SecurityMonitor:
    def __init__(self, cfg: SecurityConfig | None = None, armed: bool = False, now: float = 0.0):
        self.cfg = cfg or SecurityConfig()
        self.state = ARMED if armed else OFF
        self.since = now
        self._streak = 0
        self._last_presence = 0.0

    @property
    def armed(self) -> bool:
        return self.state != OFF

    def arm(self, now: float) -> list[dict]:
        if self.armed:
            return []
        self.state, self.since, self._streak = ARMING, now, 0
        return [{"type": "armed", "t": now}]

    def disarm(self, now: float) -> list[dict]:
        if not self.armed:
            return []
        self.state, self.since, self._streak = OFF, now, 0
        return [{"type": "disarmed", "t": now}]

    def update(self, present: bool, now: float, motion: float = 0.0) -> list[dict]:
        events = []
        if self.state == OFF:
            return events
        if present:
            self._last_presence = now
        if self.state == ARMING:
            if now - self.since >= self.cfg.exit_delay:
                self.state, self.since, self._streak = ARMED, now, 0
            return events
        if self.state == ARMED:
            self._streak = self._streak + 1 if present else 0
            if self._streak >= self.cfg.confirm_windows:
                self.state, self.since = INTRUSION, now
                events.append({"type": "intrusion", "t": now, "prob": None, "note": f"motion={motion:.4f}"})
        elif self.state == INTRUSION and now - self._last_presence >= self.cfg.quiet_seconds:
            self.state, self.since, self._streak = ARMED, now, 0
            events.append({"type": "intrusion_ended", "t": now})
        return events

    def snapshot(self) -> dict:
        return {"state": self.state, "armed": self.armed, "since": self.since}
