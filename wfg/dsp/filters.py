"""Signal cleaning for raw CSI. Time is always axis ``-2`` and subcarriers axis ``-1``."""

from __future__ import annotations

import numpy as np
from scipy import ndimage, signal

from wfg.csi.packet import DATA_SUBCARRIERS


def hampel(x: np.ndarray, window: int = 7, n_sigmas: float = 3.0, axis: int = -2) -> np.ndarray:
    """Replace outliers (spikes from AGC jumps or bad packets) with the local median."""
    size = [1] * x.ndim
    size[axis] = window
    med = ndimage.median_filter(x, size=size, mode="nearest")
    mad = ndimage.median_filter(np.abs(x - med), size=size, mode="nearest")
    sigma = 1.4826 * mad
    out = x.copy()
    mask = np.abs(x - med) > n_sigmas * np.maximum(sigma, 1e-9)
    out[mask] = med[mask]
    return out


def lowpass(x: np.ndarray, cutoff: float, fs: float, order: int = 4, axis: int = -2) -> np.ndarray:
    """Zero-phase Butterworth low-pass. Falls produce Doppler up to ~25 Hz, so keep cutoff above that."""
    sos = signal.butter(order, cutoff, btype="low", fs=fs, output="sos")
    padlen = min(3 * (2 * len(sos) + 1), x.shape[axis] - 1)
    return signal.sosfiltfilt(sos, x, axis=axis, padlen=padlen)


def sanitize_phase(csi: np.ndarray) -> np.ndarray:
    """Remove the per-packet random offset and linear slope (CFO/STO) from raw CSI phase.

    Classic linear transformation: unwrap over subcarriers, subtract the best
    fitting line. What remains is mostly multipath structure.
    """
    phase = np.unwrap(np.angle(csi), axis=-1)
    k = DATA_SUBCARRIERS.astype(float)
    slope = (phase[..., -1] - phase[..., 0]) / (k[-1] - k[0])
    offset = phase.mean(axis=-1)
    return phase - slope[..., None] * k - offset[..., None]
