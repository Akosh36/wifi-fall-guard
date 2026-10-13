"""Coarse position of a moving person from how strongly each TX-RX link is disturbed.

A person close to a link changes its CSI more than a person far from it
(see :func:`wfg.geometry.link_sensitivity`). With one transmitter and three
receivers the per-link motion energies give an estimate of where on the floor
the motion is. This is coarse: in the simulator, with the link model known
exactly, the median error is ~0.4 m; on simulated CSI it is ~0.75 m in a
4 x 3.5 m room, about as good as always guessing the room centre. Treat the
position as a zone, not a coordinate, until it is validated on real data
(see docs/security_mode.md). It only updates while the person moves; when they
stop, the last position is kept.

Steps every hop:
1. motion energy of each link over the last second (std of the cleaned amplitude);
2. remove the link's noise floor (in quadrature) and divide by its typical
   walking energy, both learned online, because links differ in sensitivity;
3. likelihood of every point of a 10 cm floor grid from the fit
   ``energy ~ a * sensitivity(position)``;
4. a grid Bayes filter: the belief from the previous hop is spread by how far
   a person can walk in one hop, then multiplied by the likelihood. Tracking
   over time removes most of the mirror ambiguities a single fit has.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from wfg.dsp.features import relative_amplitude
from wfg.geometry import RoomLayout, link_sensitivity


class LinkLocalizer:
    def __init__(self, layout: RoomLayout, fs: float, hop: float = 0.5, min_motion: float = 0.6,
                 step: float = 0.1, max_speed: float = 1.2, obs_noise: float = 0.1):
        self.layout, self.fs = layout, fs
        self.grid = layout.grid(step)  # furniture included: people sit and lie on it
        self.model = link_sensitivity(layout.link_distance(self.grid))  # (G, nodes)
        d2 = ((self.grid[:, None, :] - self.grid[None, :, :]) ** 2).sum(-1)
        k = np.exp(-0.5 * d2 / (max_speed * hop) ** 2)
        self.motion_kernel = (k / k.sum(axis=1, keepdims=True)).astype(np.float32)  # (G, G), rows sum to 1
        self.min_motion, self.obs_noise = min_motion, obs_noise
        self._hist: deque = deque(maxlen=600)  # recent energies, for noise floor and scale
        self.belief: np.ndarray | None = None
        self.pos: np.ndarray | None = None
        self.radius = 1.0

    @staticmethod
    def link_energy(csi: np.ndarray, fs: float) -> np.ndarray:
        rel = relative_amplitude(csi, fs)  # (nodes, T, 52)
        return rel.std(axis=1).mean(axis=1)

    def update(self, csi: np.ndarray, present: bool = True) -> dict | None:
        """``csi``: last ~1 s, (nodes, T, 52). Returns ``{"x", "y", "r", "moving"}`` or None."""
        e = self.link_energy(csi, self.fs)
        self._hist.append(e)
        if not present:
            self.pos, self.belief = None, None
            return None
        h = np.asarray(self._hist)
        floor = np.percentile(h, 5, axis=0)
        excess = np.sqrt(np.maximum(e ** 2 - floor ** 2, 0.0))  # noise adds in quadrature
        moving = bool((excess / (floor + 1e-9)).max() > self.min_motion) and len(h) > 10
        if moving:
            all_excess = np.sqrt(np.maximum(h ** 2 - floor ** 2, 0.0))
            o = excess / np.maximum(np.percentile(all_excess, 95, axis=0), 1e-9)  # typical walking energy
            m = self.model
            a = np.clip((m @ o) / (m * m).sum(axis=1), 0.0, None)
            res = ((o[None, :] - a[:, None] * m) ** 2).sum(axis=1)
            like = np.exp(-0.5 * (res - res.min()) / self.obs_noise ** 2)
            prior = np.full(len(self.grid), 1.0 / len(self.grid)) if self.belief is None else self.belief @ self.motion_kernel
            post = prior * like
            self.belief = post / post.sum()
            est = self.belief @ self.grid
            spread = float(np.sqrt(self.belief @ ((self.grid - est) ** 2).sum(axis=1)))
            self.pos = est
            self.radius = float(np.clip(spread, 0.3, 1.5))
        if self.pos is None:
            return None
        return {"x": round(float(self.pos[0]), 2), "y": round(float(self.pos[1]), 2),
                "r": round(self.radius, 2), "moving": moving}
