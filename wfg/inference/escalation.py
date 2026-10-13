"""What happens after a fall: watch, decide, and only then call for help.

Lying on the floor for a minute and getting up again is not an emergency, so
the server never calls an ambulance straight from the fall detector. Instead
every fall opens an *episode* with a timeline:

1. **observing** — for ``observe_seconds`` (3 minutes) the system watches
   whether the person gets up and collects breathing / heart-rate readings.
   Getting up at any point closes the episode.
2. At the end of the observation the readings decide:

   * person still down **and** vital signs abnormal → **countdown**: an
     automatic emergency call after ``cancel_seconds`` unless somebody
     cancels it;
   * person still down, vital signs normal or unknown → **asking**: the
     owner (and other approvers) get "Call an ambulance?" in the app and in
     Telegram. ``approvals_required`` "yes" answers call, one "no" closes the
     episode. Abnormal readings arriving while waiting switch to the
     countdown; no answer at all within ``no_answer_seconds`` calls as well.

3. **called** — the call was decided; the episode stays open until the
   person gets up or someone acknowledges it.

Heart rate from ESP32 CSI is experimental, so "no reading" is never treated
as abnormal: without trustworthy numbers the decision goes to a person.
The sensors are a party to the decision too: with fewer than
``min_nodes_online`` boards online there is no automatic call either.
"""

from __future__ import annotations

from dataclasses import dataclass, field

IDLE, OBSERVING, ASKING, COUNTDOWN, CALLED = "idle", "observing", "asking", "countdown", "called"
DOWN_STATES = ("fall_suspected", "alert")


@dataclass
class EscalationConfig:
    observe_seconds: float = 180.0     # watch this long after a fall before deciding
    heart_low: float = 45.0            # beats / min outside [low, high] are abnormal
    heart_high: float = 130.0
    breath_low: float = 8.0            # breaths / min outside [low, high] are abnormal
    breath_high: float = 30.0
    min_abnormal: int = 2              # abnormal readings needed (one may be noise)
    auto_call: bool = True             # abnormal vitals call automatically after the countdown
    cancel_seconds: float = 30.0       # countdown during which anyone may cancel
    approvals_required: int = 1        # "yes" answers needed when vitals are normal
    no_answer_seconds: float = 600.0   # nobody answered "Call?" for this long -> call; 0 = never
    min_nodes_online: int = 2          # fewer boards online -> no automatic decision
    number: str = "103"                # ambulance (Uzbekistan); shown on the phone and in messages
    address: str = ""                  # home address for the dispatcher
    call_webhook: str = ""             # optional URL (SIP / SMS gateway) POSTed when a call is decided


@dataclass
class Escalation:
    cfg: EscalationConfig = field(default_factory=EscalationConfig)
    state: str = IDLE
    episode: int = 0
    started_at: float | None = None
    deadline: float | None = None
    reason: str = ""
    called_by: str = ""
    answers: dict = field(default_factory=dict)       # who -> {"yes": bool, "t": float}
    readings: list = field(default_factory=list)      # vitals collected during the episode
    timeline: list = field(default_factory=list)      # [{"t", "kind", "text"}] for the app
    _wait_up: bool = False                            # episode closed while still down
    _last_vitals_t: float | None = None

    # ---- inputs -----------------------------------------------------------------------
    def update(self, fall_state: str, now: float, vitals: dict | None = None, nodes_online: int = 99,
               fall_since: float | None = None) -> list[dict]:
        """Call on every engine step with the detector state; returns emitted events."""
        down = fall_state in DOWN_STATES
        if not down:
            self._wait_up = False
            if self.state != IDLE:
                return self._close(now, "resolved", "Odam turdi, xavf bekor qilindi")
            return []
        if self.state == IDLE:
            if self._wait_up:
                return []
            self._open(fall_since or now)
        self._collect(vitals)

        if self.state == OBSERVING and now - self.started_at >= self.cfg.observe_seconds:
            return self._decide(now, nodes_online)
        if self.state == ASKING:
            if self._abnormal() and self.cfg.auto_call and nodes_online >= self.cfg.min_nodes_online:
                return self._countdown(now)
            if self.cfg.no_answer_seconds and now >= self.deadline:
                return self._call(now, "javob bo'lmadi")
        if self.state == COUNTDOWN and now >= self.deadline:
            return self._call(now, "avtomatik")
        return []

    def answer(self, who: str, yes: bool, now: float) -> list[dict]:
        """An approver answered "call an ambulance?" (or pressed call / cancel)."""
        if self.state not in (ASKING, COUNTDOWN, OBSERVING):
            return []
        self.answers[who] = {"yes": bool(yes), "t": now}
        self._log(now, "answer", f"{who}: {'chaqirilsin' if yes else 'kerak emas'}")
        if not yes:
            return self._close(now, "emergency_cancelled", f"{who} bekor qildi", by=who)
        if self.state == COUNTDOWN or self._yes() >= self.cfg.approvals_required:
            return self._call(now, who)
        return []

    def acknowledge(self, now: float, who: str = "ilova") -> list[dict]:
        """"All is fine" on the alert screen closes any open episode."""
        if self.state == IDLE:
            return []
        return self._close(now, "emergency_cancelled", f"{who}: hammasi joyida", by=who)

    # ---- decisions --------------------------------------------------------------------
    def _open(self, t: float) -> None:
        self.episode += 1
        self.state, self.started_at = OBSERVING, t
        self.deadline = t + self.cfg.observe_seconds
        self.answers, self.readings, self.timeline = {}, [], []
        self.reason = self.called_by = ""
        self._log(t, "fall", "Yiqilish aniqlandi")
        self._log(t, "observe", f"{self.cfg.observe_seconds / 60:g} daqiqa kuzatilmoqda")

    def _decide(self, now: float, nodes_online: int) -> list[dict]:
        verdict = self.vitals_verdict()
        if nodes_online < self.cfg.min_nodes_online:
            self._log(now, "sensors", f"Faqat {nodes_online} ta plata onlayn: avtomatik qaror yo'q")
        elif verdict == "abnormal" and self.cfg.auto_call:
            return self._countdown(now)
        return self._ask(now, verdict)

    def _countdown(self, now: float) -> list[dict]:
        self.state, self.deadline = COUNTDOWN, now + self.cfg.cancel_seconds
        self.reason = self._abnormal_text()
        self._log(now, "emergency", f"Xavfli: {self.reason}. {self.cfg.cancel_seconds:.0f} s dan keyin chaqiriladi")
        return [self._event("emergency", now)]

    def _ask(self, now: float, verdict: str) -> list[dict]:
        self.state = ASKING
        self.deadline = now + self.cfg.no_answer_seconds if self.cfg.no_answer_seconds else None
        self.reason = {"normal": f"yurak urishi va nafas normal ({self._vitals_text()})",
                       "unknown": "yurak urishini o'lchab bo'lmadi"}.get(verdict, verdict)
        self._log(now, "ask", f"Odam turmadi, {self.reason}. Egasidan so'raldi")
        return [self._event("ask_owner", now, verdict=verdict)]

    def _call(self, now: float, by: str) -> list[dict]:
        self.state, self.called_by, self.deadline = CALLED, by, None
        self._log(now, "call", f"Tez yordam ({self.cfg.number}) chaqirildi: {by}")
        return [self._event("emergency_call", now, by=by)]

    def _close(self, now: float, kind: str, text: str, by: str = "") -> list[dict]:
        was = self.state
        self._log(now, kind, text)
        self.state, self.deadline = IDLE, None
        self._wait_up = kind != "resolved"
        # a fall that ended within the observation needs no extra message: the detector already said "recovered"
        if kind == "resolved" and was == OBSERVING:
            return []
        return [self._event(kind, now, by=by)]

    # ---- vital signs ------------------------------------------------------------------
    def _collect(self, vitals: dict | None) -> None:
        if not vitals or vitals.get("t") is None or vitals["t"] == self._last_vitals_t:
            return
        self._last_vitals_t = vitals["t"]
        if self.started_at is not None and vitals["t"] < self.started_at:
            return  # measured before the fall
        if vitals.get("heart_bpm") is None and vitals.get("breath_bpm") is None:
            return
        self.readings.append({"t": vitals["t"], "heart": vitals.get("heart_bpm"), "breath": vitals.get("breath_bpm")})

    def _is_abnormal(self, r: dict) -> bool:
        c = self.cfg
        h, b = r.get("heart"), r.get("breath")
        return (h is not None and not c.heart_low <= h <= c.heart_high) or \
               (b is not None and not c.breath_low <= b <= c.breath_high)

    def _abnormal(self) -> bool:
        return sum(self._is_abnormal(r) for r in self.readings[-6:]) >= self.cfg.min_abnormal

    def vitals_verdict(self) -> str:
        if not self.readings:
            return "unknown"
        if self._abnormal():
            return "abnormal"
        return "normal" if any(r.get("heart") is not None for r in self.readings) else "unknown"

    def _last(self, key: str):
        vals = [r[key] for r in self.readings if r.get(key) is not None]
        return vals[-1] if vals else None

    def _vitals_text(self) -> str:
        parts = []
        if (h := self._last("heart")) is not None:
            parts.append(f"yurak {h:.0f}/daq")
        if (b := self._last("breath")) is not None:
            parts.append(f"nafas {b:.0f}/daq")
        return ", ".join(parts) or "o'lchov yo'q"

    def _abnormal_text(self) -> str:
        bad = [r for r in self.readings[-6:] if self._is_abnormal(r)]
        r = bad[-1] if bad else {}
        c = self.cfg
        if r.get("heart") is not None and not c.heart_low <= r["heart"] <= c.heart_high:
            return f"yurak urishi anomal ({r['heart']:.0f}/daq)"
        if r.get("breath") is not None:
            return f"nafas anomal ({r['breath']:.0f}/daq)"
        return "hayotiy ko'rsatkichlar anomal"

    # ---- output -----------------------------------------------------------------------
    def _yes(self) -> int:
        return sum(1 for a in self.answers.values() if a["yes"])

    def _log(self, t: float, kind: str, text: str) -> None:
        self.timeline.append({"t": t, "kind": kind, "text": text})

    def _event(self, kind: str, t: float, **extra) -> dict:
        down = t - self.started_at if self.started_at else 0.0
        return {"type": kind, "t": t, "episode": self.episode, "reason": self.reason, "number": self.cfg.number,
                "address": self.cfg.address, "down_min": round(down / 60, 1), "cancel_s": self.cfg.cancel_seconds,
                "vitals": self._vitals_text(), **extra}

    def snapshot(self) -> dict:
        return {"state": self.state, "episode": self.episode, "started_at": self.started_at,
                "deadline": self.deadline, "reason": self.reason, "called_by": self.called_by,
                "verdict": self.vitals_verdict() if self.started_at else None,
                "vitals": self._vitals_text() if self.readings else None,
                "answers": [{"who": k, **v} for k, v in self.answers.items()],
                "approvals": {"yes": self._yes(), "needed": self.cfg.approvals_required},
                "observe_seconds": self.cfg.observe_seconds, "cancel_seconds": self.cfg.cancel_seconds, "number": self.cfg.number,
                "address": self.cfg.address, "auto_call": self.cfg.auto_call,
                "timeline": self.timeline[-12:]}
