"""Room layout shared by the simulator, the localizer and the 3D view.

Coordinates are metres on the floor plan: ``x`` along the width, ``y`` along
the depth, ``z`` up. The layout comes from the ``room`` section of the config.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class RoomLayout:
    size: np.ndarray            # (3,) width, depth, height
    tx: np.ndarray              # (2,) floor position of the transmitter
    rx: np.ndarray              # (nodes, 2) floor positions of the receivers, in node order
    furniture: list[dict]

    @classmethod
    def from_config(cls, room: dict, nodes: list[int] | None = None) -> "RoomLayout":
        rx_map = {str(k): v for k, v in room["rx"].items()}
        order = [str(n) for n in nodes] if nodes is not None else sorted(rx_map, key=lambda k: int(k))
        return cls(size=np.asarray(room["size"], float), tx=np.asarray(room["tx"][:2], float),
                   rx=np.asarray([rx_map[k][:2] for k in order], float), furniture=list(room.get("furniture", [])))

    @property
    def n_links(self) -> int:
        return len(self.rx)

    def link_distance(self, p: np.ndarray) -> np.ndarray:
        """Distance from floor point(s) ``p`` (..., 2) to each TX-RX line segment -> (..., nodes)."""
        p = np.asarray(p, float)[..., None, :]
        a, b = self.tx[None, :], self.rx
        ab = b - a
        t = np.clip(((p - a) * ab).sum(-1) / (ab * ab).sum(-1), 0.0, 1.0)
        closest = a + t[..., None] * ab
        return np.linalg.norm(p - closest, axis=-1)

    def furniture_of(self, kind: str) -> dict | None:
        return next((f for f in self.furniture if f.get("kind") == kind), None)

    def blocked(self, p: np.ndarray, margin: float = 0.25) -> bool:
        for f in self.furniture:
            c = np.asarray(f["pos"], float)
            half = np.asarray(f.get("size", [1, 1]), float) / 2 + margin
            ang = np.deg2rad(f.get("rot", 0))
            d = p - c
            local = np.array([d[0] * np.cos(ang) + d[1] * np.sin(ang), -d[0] * np.sin(ang) + d[1] * np.cos(ang)])
            if np.all(np.abs(local) < half):
                return True
        return False

    def random_free_point(self, rng: np.random.Generator, margin: float = 0.4) -> np.ndarray:
        for _ in range(200):
            p = rng.uniform([margin, margin], self.size[:2] - margin)
            if not self.blocked(p):
                return p
        return self.size[:2] / 2

    def grid(self, step: float = 0.1, margin: float = 0.15) -> np.ndarray:
        xs = np.arange(margin, self.size[0] - margin + 1e-9, step)
        ys = np.arange(margin, self.size[1] - margin + 1e-9, step)
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        return np.stack([gx.ravel(), gy.ravel()], axis=1)


def link_sensitivity(d: np.ndarray, width: float = 0.6, floor: float = 0.2) -> np.ndarray:
    """How strongly a person at distance ``d`` from a link disturbs it (1 on the line, ``floor`` far away).

    A body inside the first Fresnel zones of a TX-RX link changes its CSI much
    more than a body far away; a Gaussian fall-off is a common first model.
    """
    return floor + (1 - floor) * np.exp(-0.5 * (np.asarray(d) / width) ** 2)
