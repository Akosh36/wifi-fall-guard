"""Security mode: from "someone is in the house" to a call to the police (102).

Movement in an armed house is often the owner who forgot to disarm, a relative
with a key, or a pet, so the police are never called on the first window.
Every intrusion opens an *episode*:

1. **asking** — straight away the owner (and other approvers) get "Call the
   police?" in the app, on the lock screen and in Telegram, with a camera
   snapshot when a camera is connected. "No" or disarming closes the episode.
2. **countdown** — the movement goes on for ``sustained_seconds`` with at
   least ``min_nodes_online`` boards online: somebody is really walking
   around. The police are called after ``cancel_seconds`` unless somebody
   cancels (only with ``auto_call``).
3. **called** — after a "yes" (``approvals_required`` of them), the end of the
   countdown, or no answer within ``no_answer_seconds``.

If the movement stops before anybody answers, the question stays open but
nothing is called without a person: the house may simply be empty again.
"""

from __future__ import annotations

from dataclasses import dataclass, field

IDLE, ASKING, COUNTDOWN, CALLED = "idle", "asking", "countdown", "called"


@dataclass
class PoliceConfig:
    auto_call: bool = True              # sustained movement calls after the countdown
    sustained_seconds: float = 60.0     # movement this long while armed = a real intruder
    cancel_seconds: float = 30.0        # countdown during which anyone may cancel
    approvals_required: int = 1         # "yes" answers needed to call
    no_answer_seconds: float = 180.0    # nobody answered while movement goes on -> call; 0 = never
    min_nodes_online: int = 2           # fewer boards online -> no automatic decision
    number: str = "102"                 # police (Uzbekistan)


@dataclass
class PoliceEscalation:
    cfg: PoliceConfig = field(default_factory=PoliceConfig)
    address: str = ""
    state: str = IDLE
    episode: int = 0
    started_at: float | None = None
    deadline: float | None = None
    reason: str = ""
    called_by: str = ""
    moving: bool = False
    answers: dict = field(default_factory=dict)
    timeline: list = field(default_factory=list)

    def update(self, security_state: str, now: float, nodes_online: int = 99) -> list[dict]:
        """Call on every engine step with the security monitor's state."""
        intrusion = security_state == "intrusion"
        if security_state in ("off", "arming"):
            if self.state != IDLE:
                return self._close(now, "police_cancelled", "Qo'riqlash o'chirildi", by="qo'riqlash o'chirildi")
            return []
        if self.state == IDLE:
            if intrusion and not self.moving:
                self.moving = True
                return self._open(now)
            self.moving = intrusion
            return []
        if intrusion != self.moving:
            self.moving = intrusion
            self._log(now, "motion", "Harakat davom etmoqda" if intrusion else "Harakat to'xtadi, xona bo'sh")
        if self.state == ASKING:
            if (self.moving and self.cfg.auto_call and nodes_online >= self.cfg.min_nodes_online
                    and now - self.started_at >= self.cfg.sustained_seconds):
                return self._countdown(now)
            if self.moving and self.cfg.no_answer_seconds and now - self.started_at >= self.cfg.no_answer_seconds:
                return self._call(now, "javob bo'lmadi")
        if self.state == COUNTDOWN and now >= self.deadline:
            return self._call(now, "avtomatik")
        return []

    def answer(self, who: str, yes: bool, now: float) -> list[dict]:
        if self.state not in (ASKING, COUNTDOWN):
            return []
        self.answers[who] = {"yes": bool(yes), "t": now}
        self._log(now, "answer", f"{who}: {'chaqirilsin' if yes else 'kerak emas'}")
        if not yes:
            return self._close(now, "police_cancelled", f"{who}: politsiya kerak emas", by=who)
        if self.state == COUNTDOWN or sum(a["yes"] for a in self.answers.values()) >= self.cfg.approvals_required:
            return self._call(now, who)
        return []

    def close(self, now: float, who: str) -> list[dict]:
        """The owner disarmed or acknowledged: whatever was asked is over."""
        if self.state == IDLE:
            return []
        return self._close(now, "police_cancelled", f"{who}: hammasi joyida", by=who)

    # ---- steps ------------------------------------------------------------------------
    def _open(self, now: float) -> list[dict]:
        self.episode += 1
        self.state, self.started_at, self.answers, self.timeline = ASKING, now, {}, []
        self.called_by = ""
        self.reason = "qo'riqlash rejimida uyda harakat aniqlandi"
        self.deadline = now + self.cfg.no_answer_seconds if self.cfg.no_answer_seconds else None
        self._log(now, "intrusion", "Uyda begona harakat aniqlandi")
        self._log(now, "ask", f"Egasidan so'raldi: politsiya ({self.cfg.number}) chaqirilsinmi?")
        return [self._event("police_ask", now)]

    def _countdown(self, now: float) -> list[dict]:
        self.state, self.deadline = COUNTDOWN, now + self.cfg.cancel_seconds
        self.reason = f"harakat {(now - self.started_at) / 60:.0f} daqiqadan beri to'xtamayapti"
        self._log(now, "emergency", f"Xavfli: {self.reason}. {self.cfg.cancel_seconds:.0f} s dan keyin chaqiriladi")
        return [self._event("police_countdown", now)]

    def _call(self, now: float, by: str) -> list[dict]:
        self.state, self.called_by, self.deadline = CALLED, by, None
        self._log(now, "call", f"Politsiya ({self.cfg.number}) chaqirildi: {by}")
        return [self._event("police_call", now, by=by)]

    def _close(self, now: float, kind: str, text: str, by: str) -> list[dict]:
        self._log(now, kind, text)
        self.state, self.deadline = IDLE, None
        return [self._event(kind, now, by=by)]

    def _log(self, t: float, kind: str, text: str) -> None:
        self.timeline.append({"t": t, "kind": kind, "text": text})

    def _event(self, kind: str, t: float, **extra) -> dict:
        return {"type": kind, "t": t, "episode": self.episode, "kind": "police", "reason": self.reason,
                "number": self.cfg.number, "address": self.address, "cancel_s": self.cfg.cancel_seconds,
                "down_min": round((t - self.started_at) / 60, 1) if self.started_at else 0.0, **extra}

    def snapshot(self) -> dict:
        return {"kind": "police", "state": self.state, "episode": self.episode, "started_at": self.started_at,
                "deadline": self.deadline, "reason": self.reason, "called_by": self.called_by,
                "moving": self.moving, "answers": [{"who": k, **v} for k, v in self.answers.items()],
                "approvals": {"yes": sum(a["yes"] for a in self.answers.values()),
                              "needed": self.cfg.approvals_required},
                "cancel_seconds": self.cfg.cancel_seconds, "sustained_seconds": self.cfg.sustained_seconds,
                "number": self.cfg.number, "address": self.address, "auto_call": self.cfg.auto_call,
                "timeline": self.timeline[-12:]}
