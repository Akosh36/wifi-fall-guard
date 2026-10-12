"""Domain adaptation building blocks: MMD, CORAL and adversarial (DANN) alignment.

All of them pull the encoder features of the source rooms and the new
(target) room together, so the classifier trained on source rooms keeps
working in the new room.
"""

from __future__ import annotations

import torch
import torch.nn as nn


def mmd(x: torch.Tensor, y: torch.Tensor, scales=(0.5, 1.0, 2.0, 4.0, 8.0)) -> torch.Tensor:
    """Multi-kernel Gaussian Maximum Mean Discrepancy (biased estimate)."""
    if len(x) == 0 or len(y) == 0:
        return x.new_zeros(())
    z = torch.cat([x, y])
    d2 = torch.cdist(z, z).pow(2)
    bandwidth = d2.detach().mean().clamp_min(1e-6)
    k = sum(torch.exp(-d2 / (bandwidth * s)) for s in scales)
    n = len(x)
    return k[:n, :n].mean() + k[n:, n:].mean() - 2 * k[:n, n:].mean()


def coral(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Distance between feature covariances (Deep CORAL)."""
    if len(x) < 2 or len(y) < 2:
        return x.new_zeros(())
    d = x.shape[1]
    cx = torch.cov(x.T)
    cy = torch.cov(y.T)
    return (cx - cy).pow(2).sum() / (4 * d * d)


def class_conditional_mmd(fs: torch.Tensor, ys: torch.Tensor, ft: torch.Tensor, yt: torch.Tensor) -> torch.Tensor:
    """MMD computed per class and averaged (used by KNN-MMD with pseudo-labelled target samples)."""
    losses = [mmd(fs[ys == c], ft[yt == c]) for c in torch.unique(yt) if (ys == c).any()]
    return torch.stack(losses).mean() if losses else fs.new_zeros(())


class _GradReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, alpha):
        ctx.alpha = alpha
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad):
        return -ctx.alpha * grad, None


def grad_reverse(x: torch.Tensor, alpha: float = 1.0) -> torch.Tensor:
    return _GradReverse.apply(x, alpha)


class DomainDiscriminator(nn.Module):
    """Tries to tell source-room features from target-room features (DANN)."""

    def __init__(self, dim: int, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, hidden), nn.ReLU(), nn.Dropout(0.2), nn.Linear(hidden, 1))

    def forward(self, f, alpha: float = 1.0):
        return self.net(grad_reverse(f, alpha)).squeeze(-1)
