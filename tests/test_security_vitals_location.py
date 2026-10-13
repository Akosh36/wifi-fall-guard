import numpy as np

from wfg.config import DEFAULTS
from wfg.csi.simulator import Room, ScenarioStream
from wfg.geometry import RoomLayout, link_sensitivity
from wfg.inference.localize import LinkLocalizer
from wfg.inference.security import SecurityConfig, SecurityMonitor
from wfg.inference.vitals import estimate_vitals
from wfg.server.db import Store

LAYOUT = RoomLayout.from_config(DEFAULTS["room"])


def test_link_geometry():
    d = LAYOUT.link_distance(LAYOUT.tx)
    assert np.allclose(d, 0)
    assert link_sensitivity(0.0) == 1.0 and link_sensitivity(5.0) < 0.21
    assert not LAYOUT.blocked(LAYOUT.random_free_point(np.random.default_rng(0)))


def test_security_state_machine():
    m = SecurityMonitor(SecurityConfig(exit_delay=10, confirm_windows=3, quiet_seconds=5))
    assert m.update(True, 0) == []  # off: motion is fine
    assert [e["type"] for e in m.arm(0)] == ["armed"]
    assert m.update(True, 5) == [] and m.state == "arming"  # owner still leaving
    m.update(False, 11)
    assert m.state == "armed"
    assert m.update(True, 12) == [] and m.update(True, 12.5) == []
    assert [e["type"] for e in m.update(True, 13)] == ["intrusion"]
    assert m.update(True, 14) == []  # one alarm per intrusion
    assert [e["type"] for e in m.update(False, 19.5)] == ["intrusion_ended"]
    assert [e["type"] for e in m.disarm(20)] == ["disarmed"] and m.state == "off"


def test_breathing_rate_from_simulated_csi():
    st = ScenarioStream(Room.from_seed("sim_b"), [("still", 40)], fs=100, seed=2, loop=False,
                        layout=LAYOUT, vitals=True)
    v = estimate_vitals(st.read(4000)[:, 500:], 100)
    assert v["breath_bpm"] is not None
    assert abs(v["breath_bpm"] - st.vitals_truth["breath_bpm"]) < 1.5


def test_localizer_tracks_when_link_energies_follow_the_model():
    """Algorithm check with ideal energies (real CSI is much noisier, see the module docstring)."""
    rng = np.random.default_rng(0)
    loc = LinkLocalizer(LAYOUT, 100)
    gains, floor, state = rng.uniform(0.5, 2, 3), np.full(3, 0.02), {}
    loc.link_energy = lambda csi, fs: state["e"]
    for _ in range(40):  # empty room first: learns the noise floor
        state["e"] = floor * (1 + 0.05 * rng.standard_normal(3))
        loc.update(None, present=False)
    p, target, err = LAYOUT.random_free_point(rng), LAYOUT.random_free_point(rng), []
    for k in range(400):
        d = target - p
        if np.linalg.norm(d) < 0.1:
            target = LAYOUT.random_free_point(rng)
        else:
            p = p + d / np.linalg.norm(d) * min(np.linalg.norm(d), 0.4)
        signal = gains * link_sensitivity(LAYOUT.link_distance(p)) * 0.05
        state["e"] = np.sqrt(floor ** 2 + signal ** 2)
        r = loc.update(None, present=True)
        if r and k > 100:
            err.append(np.hypot(r["x"] - p[0], r["y"] - p[1]))
    assert np.median(err) < 0.6


def test_localizer_runs_on_simulated_csi():
    st = ScenarioStream(Room.from_seed("sim_a"), [("empty", 10), ("walk", 20)], fs=100, seed=1,
                        loop=False, layout=LAYOUT)
    loc = LinkLocalizer(LAYOUT, 100)
    buf, out = np.zeros((3, 0, 52), np.complex64), []
    for _ in range(60):
        buf = np.concatenate([buf, st.read(50)], 1)[:, -100:]
        r = loc.update(buf, present=st.last_pos is not None)
        if r:
            out.append(r)
    assert out and all(0 <= r["x"] <= 4 and 0 <= r["y"] <= 3.5 and r["r"] >= 0.3 for r in out)


def test_history_and_settings_store():
    s = Store(":memory:")
    for t in range(5):
        s.add_history({"t": float(t), "state": "monitoring", "activity": "walk", "x": 1.0})
    assert [r["t"] for r in s.history(since=2)] == [3.0, 4.0]
    assert s.prune_history(3) == 3 and len(s.history()) == 2
    s.set_setting("armed", "1")
    assert s.get_setting("armed") == "1" and s.get_setting("nope", "x") == "x"
