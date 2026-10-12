import numpy as np
import pytest

from wfg.collector.hub import CSIHub
from wfg.csi.packet import CSIPacket


def feed(hub, node, n, fs=100.0, start=0.0, clock_offset=0.0, value=1.0):
    for i in range(n):
        t = start + i / fs
        hub.ingest(CSIPacket(node, i, int((t + clock_offset) * 1e6), -50, -90, 6,
                             np.full(52, value + i, dtype=np.complex64), host_time=t + 0.002))


def test_window_aligns_nodes_with_different_clocks():
    hub = CSIHub([0, 1])
    feed(hub, 0, 300, clock_offset=0.0)
    feed(hub, 1, 300, clock_offset=1234.5)  # node 1 booted at a different time
    w = hub.window(2.0)
    assert w is not None and w.shape == (2, 200, 52)
    np.testing.assert_allclose(w[0, :, 0].real, w[1, :, 0].real, atol=1.0)


def test_missing_node_gives_none():
    hub = CSIHub([0, 1])
    feed(hub, 0, 300)
    assert hub.window(2.0) is None


def test_stats_counts_loss():
    hub = CSIHub([0])
    for seq in [0, 1, 2, 5, 6]:
        hub.ingest(CSIPacket(0, seq, seq * 10000, -50, -90, 6, np.zeros(52, np.complex64), host_time=seq * 0.01))
    s = hub.stats()[0]
    assert s["loss"] == pytest.approx(2 / 7, abs=1e-3)
