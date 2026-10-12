"""Neural network models (PyTorch). Each model is an ``encoder`` that maps a CSI
window to a feature vector plus a linear ``head``; domain adaptation methods
work on the encoder features."""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn


class CNN1D(nn.Module):
    """Temporal convolutions over relative amplitude, input (B, nodes*52, T)."""

    def __init__(self, in_ch: int, dim: int = 128):
        super().__init__()

        def block(i, o, k):
            return nn.Sequential(nn.Conv1d(i, o, k, padding=k // 2), nn.BatchNorm1d(o), nn.ReLU(), nn.MaxPool1d(2))

        self.net = nn.Sequential(block(in_ch, 64, 7), block(64, 128, 5), block(128, dim, 3), block(dim, dim, 3),
                                 nn.AdaptiveAvgPool1d(1), nn.Flatten())
        self.dim = dim

    def forward(self, x):
        return self.net(x)


class CNN2D(nn.Module):
    """Convolutions over Doppler spectrograms, input (B, nodes, F, frames)."""

    def __init__(self, in_ch: int, dim: int = 64):
        super().__init__()

        def block(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(), nn.MaxPool2d(2))

        self.net = nn.Sequential(block(in_ch, 32), block(32, 64), block(64, dim),
                                 nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.dim = dim

    def forward(self, x):
        return self.net(x)


class CSITransformer(nn.Module):
    """Patches of ``patch`` time steps -> Transformer encoder -> [CLS] token. Input (B, nodes*52, T)."""

    def __init__(self, in_ch: int, dim: int = 96, patch: int = 10, depth: int = 3, heads: int = 4,
                 max_patches: int = 128, dropout: float = 0.1):
        super().__init__()
        self.embed = nn.Conv1d(in_ch, dim, kernel_size=patch, stride=patch)
        self.cls = nn.Parameter(torch.zeros(1, 1, dim))
        self.pos = nn.Parameter(torch.randn(1, max_patches + 1, dim) * 0.02)
        layer = nn.TransformerEncoderLayer(dim, heads, dim * 2, dropout, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, depth)
        self.norm = nn.LayerNorm(dim)
        self.dim = dim

    def forward(self, x):
        z = self.embed(x).transpose(1, 2)  # (B, P, dim)
        z = torch.cat([self.cls.expand(len(z), -1, -1), z], dim=1)
        z = z + self.pos[:, : z.shape[1]]
        return self.norm(self.encoder(z)[:, 0])


class FallNet(nn.Module):
    def __init__(self, encoder: nn.Module, n_classes: int):
        super().__init__()
        self.encoder = encoder
        self.head = nn.Linear(encoder.dim, n_classes)

    def features(self, x):
        return self.encoder(x)

    def forward(self, x):
        return self.head(self.encoder(x))


ARCHS = {"cnn1d": ("amp", CNN1D), "transformer": ("amp", CSITransformer), "cnn2d": ("dfs", CNN2D)}


def build_model(arch: str, in_shape: tuple, n_classes: int) -> FallNet:
    """``in_shape`` is the shape of one sample without the batch dimension."""
    if arch not in ARCHS:
        raise ValueError(f"unknown arch {arch!r}, choose from {list(ARCHS)}")
    _, cls = ARCHS[arch]
    return FallNet(cls(in_shape[0]), n_classes)


def feature_for(arch: str) -> str:
    return ARCHS[arch][0]


def save_checkpoint(path: str | Path, model: FallNet, arch: str, in_shape: tuple, classes: list[str],
                    length: int, fs: float, extra: dict | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "arch": arch, "in_shape": list(in_shape),
                "classes": classes, "length": length, "fs": fs, "feature": feature_for(arch),
                **(extra or {})}, path)


def load_checkpoint(path: str | Path, map_location: str = "cpu") -> tuple[FallNet, dict]:
    ckpt = torch.load(path, map_location=map_location, weights_only=False)
    model = build_model(ckpt["arch"], tuple(ckpt["in_shape"]), len(ckpt["classes"]))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, ckpt
