import numpy as np

from wfg import CLASSES
from wfg.inference.events import ALERT, MONITORING, SUSPECTED, DetectorConfig, FallDetector


def probs(**kw):
    p = np.full(len(CLASSES), 0.01)
    for k, v in kw.items():
        p[CLASSES.index(k)] = v
    return p / p.sum()


def test_fall_then_no_movement_raises_alert():
    d = FallDetector(CLASSES, DetectorConfig(inactivity_seconds=5, confirm_windows=2))
    assert d.update(probs(fall=0.9), 0.0) == []
    ev = d.update(probs(fall=0.9), 0.5)
    assert ev[0]["type"] == "fall_suspected" and d.state == SUSPECTED
    t, events = 1.0, []
    while t < 7:
        events += d.update(probs(still=0.9), t)
        t += 0.5
    assert any(e["type"] == "alert" for e in events) and d.state == ALERT


def test_getting_up_cancels():
    d = FallDetector(CLASSES, DetectorConfig(inactivity_seconds=30, recovery_windows=2))
    d.update(probs(fall=0.9), 0.0)
    d.update(probs(fall=0.9), 0.5)
    d.update(probs(walk=0.9), 1.0)
    ev = d.update(probs(walk=0.9), 1.5)
    assert ev[0]["type"] == "recovered" and d.state == MONITORING


def test_single_spike_is_ignored():
    d = FallDetector(CLASSES, DetectorConfig(confirm_windows=2))
    d.update(probs(fall=0.9), 0.0)
    d.update(probs(sit=0.9), 0.5)
    assert d.state == MONITORING


def test_acknowledge_resets():
    d = FallDetector(CLASSES)
    d.update(probs(fall=0.9), 0.0)
    d.update(probs(fall=0.9), 0.5)
    assert d.acknowledge(1.0)[0]["type"] == "acknowledged" and d.state == MONITORING
