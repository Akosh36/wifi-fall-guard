"""Physics-inspired WiFi CSI simulator.

Real CSI is needed for the thesis results, but a simulator lets the whole
pipeline (collector, DSP, models, domain adaptation, server, dashboard) be
developed and tested before the ESP32 hardware arrives.

Model of the channel seen by receiver ``n`` on subcarrier frequency ``f``::

    H_n(f, t) = sum_k a_k * exp(-j 2 pi f tau_k)                (static multipath: walls, furniture)
              + g_n(t) * exp(-j 2 pi (fc + f) (L_n + p_n s(t)) / c)  (path reflected by the body)
              + noise

``s(t)`` is the change of the body reflection path length (metres). Its
speed produces the Doppler shift that distinguishes a fall (fast, ~2-3 m/s,
followed by stillness) from sitting or lying down (slow). A *room* fixes the
static multipath, body-path gains, geometry factors and noise level, so
different rooms produce systematically different CSI. That is exactly the
domain shift the thesis studies.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from wfg import CLASSES
from wfg.csi.packet import DATA_SUBCARRIERS

C = 299_792_458.0
FC = 2.437e9  # channel 6
SUBCARRIER_SPACING = 312.5e3
FREQS = DATA_SUBCARRIERS * SUBCARRIER_SPACING
WAVELENGTH = C / FC


def _seed(value: int | str) -> int:
    if isinstance(value, int):
        return value
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "little")


@dataclass
class Room:
    """Random but reproducible propagation environment."""

    name: str
    n_nodes: int = 3
    static_amp: np.ndarray = field(default=None)  # (nodes, K)
    static_delay: np.ndarray = field(default=None)  # (nodes, K) seconds
    body_gain: np.ndarray = field(default=None)  # (nodes,)
    geometry: np.ndarray = field(default=None)  # (nodes,) projection of body motion on the path
    base_path: np.ndarray = field(default=None)  # (nodes,) metres
    noise: float = 0.02
    agc_jitter: float = 0.02
    scale: float = 15.0  # int8 quantisation scale, set per room so that |h| peaks near 40 like ESP32

    @classmethod
    def from_seed(cls, name: str | int, n_nodes: int = 3, nlos: bool | None = None) -> "Room":
        rng = np.random.default_rng(_seed(f"room:{name}"))
        if nlos is None:
            nlos = bool(rng.random() < 0.3)
        k = 6
        static_amp = rng.uniform(0.2, 1.0, (n_nodes, k))
        static_amp[:, 0] *= 0.3 if nlos else 1.5  # line-of-sight component
        room = cls(
            name=str(name),
            n_nodes=n_nodes,
            static_amp=static_amp,
            static_delay=rng.uniform(5e-9, 80e-9, (n_nodes, k)),
            body_gain=np.zeros(n_nodes),
            geometry=rng.uniform(0.4, 1.3, n_nodes) * rng.choice([-1, 1], n_nodes),
            base_path=rng.uniform(3.0, 9.0, n_nodes),
            noise=float(rng.uniform(0.01, 0.04)),
            agc_jitter=float(rng.uniform(0.005, 0.03)),
        )
        # body reflection is roughly 10-20 dB below the static channel (weaker without line of sight)
        level = np.abs(room.static_response()).mean(axis=1)
        room.body_gain = level * rng.uniform(0.05, 0.15 if nlos else 0.3, n_nodes)
        room.noise = float(level.mean() * rng.uniform(0.01, 0.03))
        room.scale = float(40.0 / np.abs(room.static_response()).max())  # receiver AGC
        return room

    def static_response(self) -> np.ndarray:
        """(nodes, 52) complex static channel."""
        phase = -2j * np.pi * FREQS[None, None, :] * self.static_delay[:, :, None]
        return (self.static_amp[:, :, None] * np.exp(phase)).sum(axis=1)


# --------------------------------------------------------------------------- trajectories


def _smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _breathing(t: np.ndarray, rng: np.random.Generator, amp: float = 0.004) -> np.ndarray:
    f = rng.uniform(0.2, 0.4)
    return amp * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi))


def _walking(t: np.ndarray, speed_profile: np.ndarray, fs: float, rng: np.random.Generator) -> np.ndarray:
    """Path-length change of a walking person for a given speed profile (0..1 of the walking speed).

    The person turns around every few seconds, and swinging limbs add a small
    ~2 Hz component whose size follows the speed.
    """
    v = rng.uniform(0.6, 1.3)
    period = rng.uniform(2.0, 5.0)
    direction = np.sign(np.sin(2 * np.pi * t / period + rng.uniform(0, 2 * np.pi))) * rng.choice([-1, 1])
    s = np.cumsum(v * speed_profile * direction) / fs
    limbs = 0.04 * speed_profile * np.sin(2 * np.pi * rng.uniform(1.6, 2.2) * t)
    return s + limbs


def trajectory(activity: str, duration: float, fs: float, rng: np.random.Generator,
               onset: float | None = None, context: str = "auto") -> tuple[np.ndarray, np.ndarray]:
    """Body path-length change ``s`` (m) and body gain multiplier for one activity clip.

    Transitional activities (sit, lie, fall) start at ``onset`` seconds. Before
    the onset the person stands still or (``context="auto"``, half of the time)
    walks and stops just before it, because in real life people often fall
    while walking. Walking clips sometimes include stopping or starting, so a
    model cannot mistake "stopped walking" for "fell".
    """
    n = int(round(duration * fs))
    t = np.arange(n) / fs
    gain = np.ones(n)
    if onset is None:
        onset = rng.uniform(0.6, max(0.7, duration - 2.6))
    vary = context == "auto"

    if activity == "empty":
        return np.zeros(n), np.zeros(n)
    if activity == "still":
        s = _breathing(t, rng)
        if vary and rng.random() < 0.25:  # finishes walking at the start of the clip
            stop = rng.uniform(0.3, 1.2)
            s = s + _walking(t, 1 - _smoothstep((t - stop + 0.4) / 0.4), fs, rng)
        return s, gain
    if activity == "walk":
        profile = np.ones(n)
        r = rng.random() if vary else 1.0
        if r < 0.25:  # stops walking during the clip
            stop = rng.uniform(1.5, duration - 0.5)
            profile = 1 - _smoothstep((t - stop) / 0.5)
        elif r < 0.4:  # starts walking during the clip
            start = rng.uniform(0.3, duration - 1.5)
            profile = _smoothstep((t - start) / 0.5)
        return _walking(t, profile, fs, rng) + _breathing(t, rng), gain

    rel = t - onset
    if activity == "sit":
        delta, dur, end_gain = rng.uniform(0.3, 0.5), rng.uniform(1.0, 1.8), 0.85
        s = delta * _smoothstep(rel / dur)
    elif activity == "lie":
        delta, dur, end_gain = rng.uniform(0.6, 1.0), rng.uniform(2.0, 3.5), 0.7
        s = delta * _smoothstep(rel / dur)
    elif activity == "fall":
        delta, dur, end_gain = rng.uniform(0.8, 1.3), rng.uniform(0.4, 0.8), 0.6
        x = np.clip(rel / dur, 0.0, 1.0)
        s = delta * x ** 2  # free-fall-like acceleration
        after = rel > dur
        tau = rel[after] - dur
        s[after] += 0.06 * np.exp(-tau / 0.15) * np.sin(2 * np.pi * 6 * tau)  # impact bounce
    else:
        raise ValueError(f"unknown activity {activity!r}")

    s = s + _breathing(t, rng)
    if vary and rng.random() < 0.5:  # walking until just before the transition
        w = _walking(t, 1 - _smoothstep((rel + 0.4) / 0.4), fs, rng)
        i0 = min(int(np.searchsorted(t, onset)), n - 1)
        s = s + np.where(rel < 0, w - w[i0], 0.0)  # continuous: the walk ends where the transition starts
    gain = np.where(rel < 0, 1.0, 1.0 + (end_gain - 1.0) * _smoothstep(rel / max(dur, 1e-3)))
    return s, gain


# --------------------------------------------------------------------------- synthesis


def synthesize(room: Room, s: np.ndarray, gain: np.ndarray, rng: np.random.Generator,
               phase_noise: bool = True) -> np.ndarray:
    """Complex CSI (nodes, T, 52) for a body trajectory in a room, int8-quantised like ESP32."""
    n = len(s)
    static = room.static_response()[:, None, :]  # (nodes, 1, 52)
    path = room.base_path[:, None] + room.geometry[:, None] * s[None, :]  # (nodes, T)
    body_phase = -2j * np.pi * (FC + FREQS[None, None, :]) * path[:, :, None] / C
    body = (room.body_gain[:, None] * gain[None, :])[:, :, None] * np.exp(body_phase)
    h = static + body
    h = h * (1 + room.agc_jitter * rng.standard_normal((room.n_nodes, n, 1)))  # AGC
    noise = room.noise * (rng.standard_normal(h.shape) + 1j * rng.standard_normal(h.shape)) / np.sqrt(2)
    h = h + noise
    if phase_noise:  # random CFO + timing offset per packet: corrupts raw phase, not amplitude
        offset = rng.uniform(-np.pi, np.pi, (room.n_nodes, n, 1))
        slope = rng.normal(0, 2e-8, (room.n_nodes, n, 1))
        h = h * np.exp(1j * (offset + 2 * np.pi * FREQS[None, None, :] * slope))
    h = h * room.scale
    q = np.round(h.real).clip(-128, 127) + 1j * np.round(h.imag).clip(-128, 127)
    return q.astype(np.complex64)


def simulate_clip(activity: str, room: Room, duration: float = 4.0, fs: float = 100.0,
                  rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng()
    s, gain = trajectory(activity, duration, fs, rng)
    return synthesize(room, s, gain, rng)


def simulate_dataset(rooms: list[str], clips_per_class: int = 40, duration: float = 4.0,
                     fs: float = 100.0, n_nodes: int = 3, seed: int = 0,
                     classes: list[str] | None = None):
    """Generate a labelled dataset as a list of dicts (same shape as recorded sessions)."""
    classes = classes or CLASSES
    rng = np.random.default_rng(seed)
    out = []
    for room_name in rooms:
        room = Room.from_seed(room_name, n_nodes=n_nodes)
        for label in classes:
            for i in range(clips_per_class):
                csi = simulate_clip(label, room, duration, fs, rng)
                out.append({"csi": csi, "label": label, "room": room_name,
                            "subject": f"sim{i % 5}", "fs": fs})
    return out


class ScenarioStream:
    """Continuous CSI stream following a scripted scenario, for the live demo.

    ``scenario`` is a list of ``(activity, seconds)``. Transitional activities
    are rendered with their onset at the start of the segment.
    """

    def __init__(self, room: Room, scenario: list[tuple[str, float]], fs: float = 100.0,
                 seed: int = 0, loop: bool = True):
        self.room, self.fs, self.loop = room, fs, loop
        self.rng = np.random.default_rng(seed)
        self.scenario = scenario
        self.truth: list[str] = []  # activity at every sample
        self.events: list[tuple[int, str]] = []  # (sample index of onset, transitional activity)
        self._buf = np.zeros((room.n_nodes, 0, len(FREQS)), dtype=np.complex64)
        self._seg = 0
        self._s_end, self._g_end = 0.0, 0.0

    def _render_next(self) -> bool:
        if self._seg >= len(self.scenario):
            if not self.loop:
                return False
            self._seg = 0
        activity, seconds = self.scenario[self._seg]
        self._seg += 1
        onset = 0.3 if activity in ("sit", "lie", "fall") else None
        s, gain = trajectory(activity, seconds, self.fs, self.rng, onset=onset, context="none")
        # keep the body position and gain continuous across segment boundaries
        s = s + self._s_end
        blend = np.clip(np.arange(len(gain)) / (0.5 * self.fs), 0.0, 1.0)
        gain = self._g_end + (gain - self._g_end) * blend
        self._s_end, self._g_end = float(s[-1]), float(gain[-1])
        csi = synthesize(self.room, s, gain, self.rng)
        self._buf = np.concatenate([self._buf, csi], axis=1)
        n = csi.shape[1]
        if onset is not None:  # the transition itself, then the person rests still
            self.events.append((len(self.truth) + int(onset * self.fs), activity))
            moving = min(n, int(3.5 * self.fs))
            self.truth.extend([activity] * moving + ["still"] * (n - moving))
        else:
            self.truth.extend([activity] * n)
        return True

    def read(self, n: int) -> np.ndarray | None:
        """Next ``n`` samples as (nodes, n, 52), or None when a non-looping scenario ends."""
        while self._buf.shape[1] < n:
            if not self._render_next():
                return None
        out, self._buf = self._buf[:, :n], self._buf[:, n:]
        return out


DEMO_SCENARIO = [
    ("empty", 6), ("walk", 8), ("still", 5), ("sit", 5), ("still", 4), ("walk", 6),
    ("lie", 6), ("still", 5), ("walk", 6), ("fall", 40), ("walk", 8), ("empty", 6),
]


TRANSITIONS = ("sit", "lie", "fall")


def random_scenario(rng: np.random.Generator, n_segments: int = 12) -> list[tuple[str, float]]:
    """Plausible random day-in-the-life sequence used to make streaming training windows."""
    lengths = {"empty": (4, 8), "still": (3, 8), "walk": (4, 10), "sit": (5, 8), "lie": (6, 10), "fall": (8, 15)}
    out, prev = [], "walk"
    for _ in range(n_segments):
        if prev in TRANSITIONS or prev == "empty":
            act = "walk"  # after sitting, lying, falling or entering the room the person walks next
        else:
            act = rng.choice(["still", "walk", "sit", "lie", "fall", "empty"], p=[.15, .25, .15, .15, .2, .1])
        out.append((str(act), float(rng.uniform(*lengths[act]))))
        prev = act
    return out


def stream_windows(room: Room, rng: np.random.Generator, n_segments: int = 12, win: float = 4.0,
                   hop: float = 1.0, fs: float = 100.0) -> list[dict]:
    """Label sliding windows of a continuous random scenario the way the real-time engine sees them.

    A window is labelled with a transition (sit / lie / fall) when its onset lies
    between 0.2 s before the window start and 1.0 s before its end; otherwise with
    the activity at the end of the window. Training on these windows teaches
    the model the situations that clip recordings miss (a fall right after
    walking, the end of a walk, a person resting after lying down).
    """
    stream = ScenarioStream(room, random_scenario(rng, n_segments), fs=fs,
                            seed=int(rng.integers(1 << 31)), loop=False)
    chunks = []
    while (c := stream.read(int(fs))) is not None:
        chunks.append(c)
    data = np.concatenate(chunks, axis=1)
    n_win, n_hop = int(win * fs), int(hop * fs)
    out = []
    for start in range(0, data.shape[1] - n_win + 1, n_hop):
        end = start + n_win
        label = stream.truth[end - 1]
        for onset, act in stream.events:
            if start - 0.2 * fs <= onset <= end - 1.0 * fs:
                label = act
                if act == "fall":
                    break
        if label in TRANSITIONS and not any(start - 0.2 * fs <= o <= end - fs for o, _ in stream.events):
            last = max((o for o, _ in stream.events if o < end), default=0)
            # transition only just starting: still the previous activity; finished long ago: resting
            label = stream.truth[max(last - 1, 0)] if last > end - fs else "still"
            if label in TRANSITIONS:
                label = "still"
        out.append({"csi": data[:, start:end], "label": label, "room": room.name, "subject": "stream", "fs": fs})
    return out
