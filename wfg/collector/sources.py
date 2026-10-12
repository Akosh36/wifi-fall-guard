"""Packet sources that feed a :class:`CSIHub`: real ESP32 nodes over UDP, or the simulator."""

from __future__ import annotations

import logging
import socket
import threading
import time

from wfg.collector.hub import CSIHub
from wfg.csi import packet as pk
from wfg.csi.simulator import DEMO_SCENARIO, Room, ScenarioStream

log = logging.getLogger(__name__)


class UDPSource:
    """Receives packets from the ``csi_rx`` firmware on ``host:port``."""

    def __init__(self, hub: CSIHub, host: str = "0.0.0.0", port: int = 5500):
        self.hub, self.host, self.port = hub, host, port
        self.bad_packets = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "UDPSource":
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._run, name="udp-csi", daemon=True)
        self._thread.start()
        log.info("listening for CSI on udp://%s:%d", self.host, self.port)
        return self

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                data, _ = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self.hub.ingest(pk.parse(data, time.time()))
            except ValueError:
                self.bad_packets += 1

    def stop(self) -> None:
        self._stop.set()
        self._sock.close()
        if self._thread:
            self._thread.join(timeout=2)


class SimSource:
    """Plays a scripted scenario in real time, as if three ESP32 nodes were sending.

    ``truth`` exposes the activity currently being simulated so the dashboard
    can show ground truth next to the prediction during a demo.
    """

    def __init__(self, hub: CSIHub, room: str = "demo", scenario=None, fs: float = 100.0,
                 speed: float = 1.0, seed: int = 0, n_nodes: int = 3):
        self.hub, self.fs, self.speed = hub, fs, speed
        self.stream = ScenarioStream(Room.from_seed(room, n_nodes=n_nodes), scenario or DEMO_SCENARIO,
                                     fs=fs, seed=seed)
        self.n_nodes = n_nodes
        self.truth = "empty"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seq = 0

    def start(self) -> "SimSource":
        self._thread = threading.Thread(target=self._run, name="sim-csi", daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        chunk = int(self.fs / 10)  # 100 ms of samples per tick
        t0 = time.time()
        sent = 0
        while not self._stop.is_set():
            block = self.stream.read(chunk)
            if block is None:
                break
            truth_tail = self.stream.truth
            self.truth = truth_tail[sent + chunk - 1] if len(truth_tail) > sent + chunk - 1 else self.truth
            for i in range(chunk):
                sim_t = (sent + i) / self.fs
                host_t = t0 + sim_t / self.speed
                for n in range(self.n_nodes):
                    pkt = pk.CSIPacket(node_id=n, seq=self._seq, esp_time_us=int(sim_t * 1e6 / self.speed) + n * 1_000_000,
                                       rssi=-45 - 5 * n, noise_floor=-92, channel=6, csi=block[n, i],
                                       host_time=host_t)
                    self.hub.ingest(pkt)
                self._seq += 1
            sent += chunk
            delay = t0 + sent / self.fs / self.speed - time.time()
            if delay > 0:
                time.sleep(delay)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
