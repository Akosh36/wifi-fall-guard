"""Binary UDP packet format sent by the ESP32-S3 receiver firmware.

The layout must stay in sync with ``firmware/csi_rx/main/main.c``.

Header (little endian, 20 bytes)::

    u16  magic        0xC51A
    u8   version      1
    u8   node_id      receiver id (0..255)
    u32  seq          per-node packet counter
    u64  esp_time_us  esp_timer_get_time() on the node
    i8   rssi         dBm
    i8   noise_floor  dBm
    u8   channel      WiFi channel
    u8   n_raw        number of raw complex values that follow

Payload: ``n_raw`` pairs of int8 ``(imag, real)``, exactly as the ESP32 CSI
buffer stores them. For an HT20 legacy LTF buffer ``n_raw`` is 64 and the
values are FFT bins in the order 0..31, -32..-1.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np

MAGIC = 0xC51A
VERSION = 1
HEADER = struct.Struct("<HBBIQbbBB")
HEADER_SIZE = HEADER.size  # 20

# Data subcarrier indices of a 20 MHz OFDM symbol (DC and guards removed).
DATA_SUBCARRIERS = np.array([i for i in range(-26, 27) if i != 0])
N_SUBCARRIERS = len(DATA_SUBCARRIERS)  # 52


@dataclass
class CSIPacket:
    node_id: int
    seq: int
    esp_time_us: int
    rssi: int
    noise_floor: int
    channel: int
    csi: np.ndarray  # complex64, shape (52,)
    host_time: float = 0.0


def raw_to_subcarriers(raw: np.ndarray) -> np.ndarray:
    """Map 64 raw FFT bins (ESP32 order 0..31, -32..-1) to the 52 data subcarriers."""
    if raw.shape[-1] < 64:
        raise ValueError(f"expected at least 64 raw bins, got {raw.shape[-1]}")
    idx = np.where(DATA_SUBCARRIERS >= 0, DATA_SUBCARRIERS, 64 + DATA_SUBCARRIERS)
    return raw[..., idx]


def subcarriers_to_raw(csi: np.ndarray) -> np.ndarray:
    """Inverse of :func:`raw_to_subcarriers` (guards and DC are zero)."""
    raw = np.zeros(csi.shape[:-1] + (64,), dtype=np.complex64)
    idx = np.where(DATA_SUBCARRIERS >= 0, DATA_SUBCARRIERS, 64 + DATA_SUBCARRIERS)
    raw[..., idx] = csi
    return raw


def parse(data: bytes, host_time: float = 0.0) -> CSIPacket:
    if len(data) < HEADER_SIZE:
        raise ValueError("packet shorter than header")
    magic, version, node_id, seq, esp_t, rssi, noise, channel, n_raw = HEADER.unpack_from(data)
    if magic != MAGIC:
        raise ValueError(f"bad magic 0x{magic:04x}")
    if version != VERSION:
        raise ValueError(f"unsupported version {version}")
    payload = data[HEADER_SIZE:HEADER_SIZE + 2 * n_raw]
    if len(payload) != 2 * n_raw:
        raise ValueError("truncated payload")
    iq = np.frombuffer(payload, dtype=np.int8).astype(np.float32).reshape(-1, 2)
    raw = (iq[:, 1] + 1j * iq[:, 0]).astype(np.complex64)  # stored as (imag, real)
    return CSIPacket(node_id, seq, esp_t, rssi, noise, channel, raw_to_subcarriers(raw), host_time)


def pack(pkt: CSIPacket) -> bytes:
    """Serialize a packet the same way the firmware does (used by the simulator and tests)."""
    raw = subcarriers_to_raw(pkt.csi)
    iq = np.empty((64, 2), dtype=np.int8)
    iq[:, 0] = np.clip(np.round(raw.imag), -128, 127)
    iq[:, 1] = np.clip(np.round(raw.real), -128, 127)
    header = HEADER.pack(MAGIC, VERSION, pkt.node_id, pkt.seq & 0xFFFFFFFF, pkt.esp_time_us,
                         pkt.rssi, pkt.noise_floor, pkt.channel, 64)
    return header + iq.tobytes()
