"""Interpretable baseline: hand-crafted CSI features + multinomial logistic regression.

Pure NumPy, so it runs on a Raspberry Pi without PyTorch and gives the
reference numbers the deep models in :mod:`wfg.models` must beat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from wfg import CLASSES
from wfg.dsp.features import CLASSIC_FEATURE_NAMES, classic_features


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


@dataclass
class ClassicModel:
    classes: list[str] = field(default_factory=lambda: list(CLASSES))
    l2: float = 1e-3
    lr: float = 0.5
    epochs: int = 600
    mean: np.ndarray | None = None
    std: np.ndarray | None = None
    w: np.ndarray | None = None
    b: np.ndarray | None = None
    fs: float = 100.0

    # -- training -----------------------------------------------------------------
    def fit(self, x: np.ndarray, y: np.ndarray, class_weight: str | None = "balanced") -> "ClassicModel":
        x = np.asarray(x, dtype=np.float64)
        self.mean, self.std = x.mean(axis=0), x.std(axis=0) + 1e-6
        xs = (x - self.mean) / self.std
        n, d = xs.shape
        k = len(self.classes)
        onehot = np.eye(k)[y]
        if class_weight == "balanced":
            counts = np.bincount(y, minlength=k).astype(float)
            sw = (n / (k * np.maximum(counts, 1)))[y]
        else:
            sw = np.ones(n)
        self.w, self.b = np.zeros((d, k)), np.zeros(k)
        for _ in range(self.epochs):  # full-batch gradient descent, small data
            p = _softmax(xs @ self.w + self.b)
            g = (p - onehot) * sw[:, None] / sw.sum()
            self.w -= self.lr * (xs.T @ g + self.l2 * self.w)
            self.b -= self.lr * g.sum(axis=0)
        return self

    # -- inference ----------------------------------------------------------------
    def predict_proba_features(self, x: np.ndarray, domain_stats: tuple | None = None) -> np.ndarray:
        """``domain_stats=(mean, std)`` re-standardises with target-room statistics (unsupervised adaptation)."""
        mean, std = domain_stats if domain_stats is not None else (self.mean, self.std)
        xs = (np.atleast_2d(x) - mean) / std
        return _softmax(xs @ self.w + self.b)

    def predict_proba(self, csi: np.ndarray) -> np.ndarray:
        """Probabilities for one aligned CSI window (nodes, T, 52)."""
        return self.predict_proba_features(classic_features(csi, self.fs))[0]

    # -- persistence --------------------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, mean=self.mean, std=self.std, w=self.w, b=self.b,
                 meta=json.dumps({"kind": "classic", "classes": self.classes, "fs": self.fs,
                                  "features": CLASSIC_FEATURE_NAMES}))

    @classmethod
    def load(cls, path: str | Path) -> "ClassicModel":
        d = np.load(path, allow_pickle=False)
        meta = json.loads(str(d["meta"]))
        return cls(classes=meta["classes"], mean=d["mean"], std=d["std"], w=d["w"], b=d["b"], fs=meta["fs"])
