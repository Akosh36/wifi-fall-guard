import numpy as np

from wfg.dsp.features import (CLASSIC_FEATURE_NAMES, classic_features, doppler_spectrogram, fix_length,
                              relative_amplitude)
from wfg.dsp.filters import hampel, sanitize_phase
from wfg.csi.packet import DATA_SUBCARRIERS
from wfg.csi.simulator import simulate_clip, synthesize, trajectory


def test_hampel_removes_spike():
    x = np.zeros((1, 100, 3))
    x[0, 50, 1] = 100.0
    assert hampel(x)[0, 50, 1] == 0.0


def test_sanitize_phase_removes_linear_offset():
    k = DATA_SUBCARRIERS
    csi = np.exp(1j * (0.7 + 0.05 * k))[None, :]
    np.testing.assert_allclose(sanitize_phase(csi), 0.0, atol=1e-6)


def test_feature_shapes(room, rng):
    csi = simulate_clip("walk", room, rng=rng)
    rel = relative_amplitude(csi)
    assert rel.shape == csi.shape
    dfs = doppler_spectrogram(rel)
    assert dfs.shape[0] == 3 and dfs.ndim == 3 and np.isfinite(dfs).all()
    f = classic_features(csi)
    assert f.shape == (len(CLASSIC_FEATURE_NAMES),) and np.isfinite(f).all()


def test_fall_has_more_high_doppler_energy_than_sitting(room):
    """A fall is fast, so more of its spectrogram energy sits in the upper half of the band."""
    rng = np.random.default_rng(3)

    def high_share(act):
        out = []
        for _ in range(6):
            s, g = trajectory(act, 4.0, 100.0, rng, onset=1.0, context="none")
            e = np.expm1(doppler_spectrogram(relative_amplitude(synthesize(room, s, g, rng)))).sum(axis=(0, 2))
            out.append(e[len(e) // 2:].sum() / e.sum())
        return np.mean(out)

    assert high_share("fall") > 3 * high_share("sit")


def test_fix_length_crops_and_pads():
    x = np.ones((2, 300, 52))
    assert fix_length(x, 400).shape == (2, 400, 52)
    assert fix_length(x, 200).shape == (2, 200, 52)
