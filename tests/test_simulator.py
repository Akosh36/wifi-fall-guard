import numpy as np

from wfg import CLASSES
from wfg.csi.simulator import Room, ScenarioStream, simulate_clip, stream_windows


def test_clip_shape_and_int8_range(room, rng):
    csi = simulate_clip("fall", room, duration=4.0, rng=rng)
    assert csi.shape == (3, 400, 52) and csi.dtype == np.complex64
    assert np.abs(csi.real).max() <= 128 and np.abs(csi.imag).max() <= 128


def test_rooms_are_reproducible_and_different():
    a1, a2, b = Room.from_seed("a"), Room.from_seed("a"), Room.from_seed("b")
    np.testing.assert_array_equal(a1.static_amp, a2.static_amp)
    assert not np.allclose(a1.static_amp, b.static_amp)


def test_empty_room_moves_less_than_walking(room, rng):
    def motion(act):
        return np.abs(simulate_clip(act, room, rng=rng)).std(axis=1).mean()
    assert motion("walk") > 2 * motion("empty")


def test_stream_is_continuous(room):
    s = ScenarioStream(room, [("walk", 2.0), ("fall", 3.0)], loop=False)
    block = s.read(500)
    assert block.shape == (3, 500, 52)
    assert s.read(10) is None
    assert s.events and s.events[0][1] == "fall"


def test_stream_windows_labels(room, rng):
    wins = stream_windows(room, rng, n_segments=6)
    assert wins and all(w["label"] in CLASSES for w in wins)
    assert all(w["csi"].shape == (3, 400, 52) for w in wins)
