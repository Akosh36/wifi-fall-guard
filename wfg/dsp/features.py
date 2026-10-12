"""Feature extraction from aligned CSI windows of shape (nodes, T, 52)."""

from __future__ import annotations

import numpy as np
from scipy import signal

from wfg.dsp.filters import hampel, lowpass

EPS = 1e-8


def relative_amplitude(csi: np.ndarray, fs: float = 100.0, cutoff: float = 35.0) -> np.ndarray:
    """Cleaned amplitude variation relative to the static channel, (nodes, T, 52).

    Dividing by the mean amplitude makes the motion signal roughly independent
    of how strong the link is in a particular room, a first, simple step
    towards cross-room robustness.
    """
    amp = np.abs(csi).astype(np.float64)
    amp = hampel(amp)
    if amp.shape[-2] > 30:
        amp = lowpass(amp, cutoff, fs)
    mean = amp.mean(axis=-2, keepdims=True)
    level = amp.mean(axis=(-2, -1), keepdims=True)
    return ((amp - mean) / (level + EPS)).astype(np.float32)


def motion_components(rel: np.ndarray, n_comp: int = 3) -> np.ndarray:
    """PCA over subcarriers per node: (nodes, n_comp, T). Most body motion lands in the first components."""
    nodes, t, _ = rel.shape
    out = np.zeros((nodes, n_comp, t), dtype=np.float32)
    for n in range(nodes):
        x = rel[n] - rel[n].mean(axis=0)
        try:
            u, s, _ = np.linalg.svd(x, full_matrices=False)
        except np.linalg.LinAlgError:
            continue
        k = min(n_comp, len(s))
        out[n, :k] = (u[:, :k] * s[:k]).T
    return out


def doppler_spectrogram(rel: np.ndarray, fs: float = 100.0, nperseg: int = 64, hop: int = 8,
                        n_comp: int = 3, fmax: float = 45.0) -> np.ndarray:
    """Log-power spectrogram of motion components summed per node: (nodes, F, frames).

    Body speed v gives an amplitude oscillation at about 2v/lambda Hz
    (lambda = 12.3 cm at 2.4 GHz), so a 2.5 m/s fall shows up near 20-40 Hz
    while sitting stays under ~8 Hz.
    """
    comps = motion_components(rel, n_comp)
    f, _, z = signal.stft(comps, fs=fs, nperseg=nperseg, noverlap=nperseg - hop, axis=-1,
                          boundary=None, padded=False)
    power = (np.abs(z) ** 2).sum(axis=1)  # sum over components -> (nodes, F, frames)
    keep = (f > 0.5) & (f <= fmax)
    return np.log1p(power[:, keep, :] * 1e3).astype(np.float32)


BANDS = [(0.1, 1.0), (1.0, 4.0), (4.0, 10.0), (10.0, 20.0), (20.0, 45.0)]
CLASSIC_FEATURE_NAMES = (
    [f"{agg}_{name}" for agg in ("mean", "max") for name in
     ["log_var", "log_peak_energy", "peak_to_mean", "after_to_peak", "peak_pos", "max_doppler_hz"]
     + [f"band_{lo:g}_{hi:g}" for lo, hi in BANDS]]
)


def classic_features(csi: np.ndarray, fs: float = 100.0) -> np.ndarray:
    """Hand-crafted features for the interpretable baseline model (no deep learning needed)."""
    rel = relative_amplitude(csi, fs)
    comp = motion_components(rel, 1)[:, 0, :]  # (nodes, T)
    t = comp.shape[-1]
    seg = max(int(0.5 * fs), 1)
    per_node = []
    for x in comp:
        var = x.var() + EPS
        n_seg = t // seg
        energy = (x[: n_seg * seg].reshape(n_seg, seg) ** 2).mean(axis=1) + EPS
        peak = int(energy.argmax())
        after = energy[min(peak + 2, n_seg - 1):].mean() if peak + 2 < n_seg else energy[-1]
        f, pxx = signal.welch(x, fs=fs, nperseg=min(128, t))
        total = pxx[(f > 0.1)].sum() + EPS
        bands = [pxx[(f > lo) & (f <= hi)].sum() / total for lo, hi in BANDS]
        # highest frequency holding a meaningful share of the energy in the most active 1 s
        lo_i, hi_i = max(0, (peak - 1) * seg), min(t, (peak + 1) * seg)
        f2, p2 = signal.welch(x[lo_i:hi_i], fs=fs, nperseg=min(64, hi_i - lo_i))
        cum = np.cumsum(p2) / (p2.sum() + EPS)
        max_dopp = float(f2[min(np.searchsorted(cum, 0.9), len(f2) - 1)])
        per_node.append([np.log(var), np.log(energy.max()), energy.max() / energy.mean(),
                         after / energy.max(), peak / max(n_seg - 1, 1), max_dopp] + bands)
    arr = np.asarray(per_node, dtype=np.float32)
    return np.concatenate([arr.mean(axis=0), arr.max(axis=0)])


def windows(n_samples: int, win: int, hop: int) -> list[slice]:
    return [slice(s, s + win) for s in range(0, n_samples - win + 1, hop)]


def fix_length(csi: np.ndarray, length: int) -> np.ndarray:
    """Centre-crop or edge-pad the time axis (-2) to ``length``."""
    t = csi.shape[-2]
    if t == length:
        return csi
    if t > length:
        start = (t - length) // 2
        return csi[..., start:start + length, :]
    pad = length - t
    width = [(0, 0)] * csi.ndim
    width[-2] = (pad // 2, pad - pad // 2)
    return np.pad(csi, width, mode="edge")
