import numpy as np
import pytest

from wfg.csi import packet as pk


def test_roundtrip_matches_firmware_layout():
    csi = (np.arange(52) - 26 + 1j * (26 - np.arange(52))).astype(np.complex64)
    raw = pk.pack(pk.CSIPacket(node_id=2, seq=7, esp_time_us=123456, rssi=-40, noise_floor=-95, channel=6, csi=csi))
    assert len(raw) == pk.HEADER_SIZE + 128 == 148
    out = pk.parse(raw, host_time=1.5)
    assert (out.node_id, out.seq, out.esp_time_us, out.rssi, out.channel) == (2, 7, 123456, -40, 6)
    np.testing.assert_allclose(out.csi, csi)
    assert out.host_time == 1.5


def test_raw_bin_order_is_esp32_order():
    raw = np.arange(64).astype(np.complex64)  # value == FFT bin index
    sc = pk.raw_to_subcarriers(raw)
    # subcarrier -26 lives in bin 64-26=38, subcarrier +1 in bin 1, +26 in bin 26
    assert sc[0].real == 38 and sc[26].real == 1 and sc[-1].real == 26


@pytest.mark.parametrize("data", [b"", b"\x00" * 30])
def test_rejects_garbage(data):
    with pytest.raises(ValueError):
        pk.parse(data)
