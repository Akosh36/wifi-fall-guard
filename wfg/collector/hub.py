"""Buffers CSI packets from several ESP32 nodes and serves time-aligned windows.

Each node has its own clock, and UDP arrival times jitter by a few
milliseconds. A node's clock offset is estimated as the smallest observed
``host_time - esp_time`` (the packet that suffered the least network delay),
so samples from different nodes can be placed on one common time axis.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from wfg.csi.packet import CSIPacket


@dataclass
class NodeBuffer:
    node_id: int
    capacity: int = 100 * 120  # two minutes at 100 Hz
    times: deque = field(default_factory=deque)
    csi: deque = field(default_factory=deque)
    rssi: deque = field(default_factory=deque)
    offset: float | None = None
    last_seq: int | None = None
    received: int = 0
    lost: int = 0
    last_host_time: float = 0.0

    def add(self, pkt: CSIPacket) -> None:
        esp_s = pkt.esp_time_us / 1e6
        cand = pkt.host_time - esp_s
        # track the minimum delay, but let it creep upwards slowly to follow clock drift
        if self.offset is None or cand < self.offset:
            self.offset = cand
        else:
            self.offset += 1e-6
        if self.last_seq is not None:
            gap = (pkt.seq - self.last_seq) & 0xFFFFFFFF
            if 1 < gap < 10_000:
                self.lost += gap - 1
            elif gap == 0 or gap >= 10_000:  # duplicate or node rebooted
                self.times.clear(); self.csi.clear(); self.rssi.clear()
                self.offset = cand
        self.last_seq = pkt.seq
        self.received += 1
        self.last_host_time = pkt.host_time
        self.times.append(esp_s + self.offset)
        self.csi.append(pkt.csi)
        self.rssi.append(pkt.rssi)
        while len(self.times) > self.capacity:
            self.times.popleft(); self.csi.popleft(); self.rssi.popleft()


class CSIHub:
    """Thread-safe store of all nodes; the UDP receiver writes, inference and recorder read."""

    def __init__(self, node_ids: list[int] | None = None, fs: float = 100.0):
        self.fs = fs
        self.expected = list(node_ids) if node_ids else None
        self.nodes: dict[int, NodeBuffer] = {}
        self._lock = threading.Lock()

    def ingest(self, pkt: CSIPacket) -> None:
        if not pkt.host_time:
            pkt.host_time = time.time()
        with self._lock:
            buf = self.nodes.get(pkt.node_id)
            if buf is None:
                buf = self.nodes[pkt.node_id] = NodeBuffer(pkt.node_id)
            buf.add(pkt)

    def node_ids(self) -> list[int]:
        return self.expected if self.expected else sorted(self.nodes)

    def latest_time(self) -> float:
        with self._lock:
            ts = [b.times[-1] for b in self.nodes.values() if b.times]
        return min(ts) if ts else 0.0

    def window(self, seconds: float, end: float | None = None, partial: bool = False) -> np.ndarray | None:
        """(nodes, T, 52) complex window on a uniform grid, or None if a node lacks data.

        Uses the nearest earlier sample (zero-order hold) for every grid point, so
        a few lost packets are tolerated; gaps longer than 0.2 s make it fail.
        With ``partial`` a silent node is left out instead (4-6 boards: one flat
        battery must not stop fall detection); None only when no node has data.
        """
        n = int(round(seconds * self.fs))
        end = self._latest_time(partial) if end is None else end
        if not end:
            return None
        grid = end - (n - 1 - np.arange(n)) / self.fs
        rows = []
        with self._lock:
            for nid in self.node_ids():
                row = self._resample(self.nodes.get(nid), grid)
                if row is None and not partial:
                    return None
                if row is not None:
                    rows.append(row)
        if not rows:
            return None
        return np.stack(rows).astype(np.complex64)

    def _latest_time(self, partial: bool) -> float:
        if not partial:
            return self.latest_time()
        # newest time all *live* nodes have reached; a node silent for over 2 s does not hold the others back
        with self._lock:
            ts = [b.times[-1] for b in self.nodes.values() if b.times]
        if not ts:
            return 0.0
        return min(t for t in ts if t > max(ts) - 2.0)

    @staticmethod
    def _resample(buf, grid: np.ndarray) -> np.ndarray | None:
        if buf is None or len(buf.times) < 2:
            return None
        t = np.fromiter(buf.times, dtype=np.float64)
        if t[0] > grid[0] or t[-1] < grid[-1] - 0.2:
            return None
        idx = np.clip(np.searchsorted(t, grid, side="right") - 1, 0, len(t) - 1)
        if np.max(grid - t[idx]) > 0.2:
            return None
        start = int(idx[0])
        data = np.asarray([buf.csi[j] for j in range(start, int(idx[-1]) + 1)])
        return data[idx - start]

    def stats(self) -> list[dict]:
        now = time.time()
        rows = []
        with self._lock:
            for nid in self.node_ids():
                b = self.nodes.get(nid)
                if b is None:
                    rows.append({"node": nid, "online": False, "rate_hz": 0.0, "loss": 0.0, "rssi": None})
                    continue
                recent = sum(1 for t in reversed(b.times) if t > b.times[-1] - 2.0) if b.times else 0
                rate = recent / 2.0
                total = b.received + b.lost
                rows.append({
                    "node": nid,
                    "online": now - b.last_host_time < 2.0,
                    "rate_hz": round(rate, 1),
                    "loss": round(b.lost / total, 4) if total else 0.0,
                    "rssi": int(np.mean(list(b.rssi)[-50:])) if b.rssi else None,
                })
        return rows
