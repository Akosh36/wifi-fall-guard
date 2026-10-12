"""Uniform prediction interface over the NumPy baseline and the PyTorch models."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from wfg.dsp.features import doppler_spectrogram, fix_length, relative_amplitude


class Predictor:
    classes: list[str]
    window_seconds: float
    fs: float

    def predict(self, csi: np.ndarray) -> np.ndarray:  # (nodes, T, 52) -> probabilities
        raise NotImplementedError


class ClassicPredictor(Predictor):
    def __init__(self, path: str | Path, window_seconds: float = 4.0):
        from wfg.baseline.classic import ClassicModel
        self.model = ClassicModel.load(path)
        self.classes, self.fs, self.window_seconds = self.model.classes, self.model.fs, window_seconds

    def predict(self, csi):
        return self.model.predict_proba(csi)


class TorchPredictor(Predictor):
    def __init__(self, path: str | Path, device: str = "cpu"):
        import torch
        from wfg.models.nets import load_checkpoint
        self._torch = torch
        self.model, ck = load_checkpoint(path, device)
        self.device = device
        self.classes, self.fs, self.length, self.feature = ck["classes"], ck["fs"], ck["length"], ck["feature"]
        self.window_seconds = self.length / self.fs

    def predict(self, csi):
        csi = fix_length(csi, self.length)
        rel = relative_amplitude(csi, self.fs)
        x = rel.transpose(0, 2, 1).reshape(-1, rel.shape[1]) if self.feature == "amp" else doppler_spectrogram(rel, self.fs)
        with self._torch.no_grad():
            logits = self.model(self._torch.as_tensor(x[None], dtype=self._torch.float32, device=self.device))
            return self._torch.softmax(logits, dim=1)[0].cpu().numpy()


def load_predictor(path: str | Path) -> Predictor:
    path = Path(path)
    if path.suffix == ".npz":
        return ClassicPredictor(path)
    if path.suffix in (".pt", ".pth"):
        return TorchPredictor(path)
    raise ValueError(f"unknown model file type: {path}")
