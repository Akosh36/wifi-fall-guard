"""Breathing and heart rate from CSI amplitude while the person is resting.

Chest motion modulates the body reflection: breathing moves the chest ~4-6 mm
(0.1-0.6 Hz), the heartbeat only ~0.2-0.5 mm (0.8-2.2 Hz). Breathing is
well established for WiFi CSI. Heart rate from a single-antenna ESP32 is at
the edge of what amplitude data allows, so it is reported only with a quality
score and must be validated against a reference device (pulse oximeter or
smartwatch) before any claim is made.

Method (per window of ~30 s):
1. amplitude of every node and subcarrier, mean removed;
2. band-pass to the band of interest;
3. keep the subcarriers with the most power in that band, merge them with PCA;
4. the spectral peak gives the rate; peak-to-median power in the band gives the quality.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

BREATH_BAND = (0.1, 0.6)
HEART_BAND = (0.8, 2.2)


@dataclass
class VitalsConfig:
    window_seconds: float = 30.0
    top_subcarriers: int = 24
    breath_min_quality: float = 4.0
    heart_min_quality: float = 10.0


def _bandpass(x: np.ndarray, band: tuple[float, float], fs: float) -> np.ndarray:
    sos = signal.butter(4, band, btype="band", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x, axis=0)


def _merged(x: np.ndarray, band: tuple[float, float], fs: float, top: int) -> np.ndarray:
    """(T, channels) -> one band-limited signal: strongest channels merged by their first principal component."""
    y = _bandpass(x, band, fs)
    power = y.var(axis=0)
    keep = np.argsort(power)[::-1][:top]
    y = y[:, keep]
    y = y / (y.std(axis=0) + 1e-12)
    u, s, _ = np.linalg.svd(y - y.mean(axis=0), full_matrices=False)
    return u[:, 0] * s[0]


def _peak(x: np.ndarray, band: tuple[float, float], fs: float, exclude: list[float] = ()) -> tuple[float, float]:
    n = len(x)
    nfft = max(8192, 1 << int(np.ceil(np.log2(n))))
    spec = np.abs(np.fft.rfft(x * np.hanning(n), nfft)) ** 2
    f = np.fft.rfftfreq(nfft, 1 / fs)
    m = (f >= band[0]) & (f <= band[1])
    for e in exclude:  # breathing harmonics leak into the heart band
        m &= np.abs(f - e) > 0.06
    if not m.any():
        return float("nan"), 0.0
    fb, pb = f[m], spec[m]
    i = int(pb.argmax())
    quality = float(pb[i] / (np.median(pb) + 1e-12))
    return float(fb[i]), quality


def estimate_vitals(csi: np.ndarray, fs: float, cfg: VitalsConfig | None = None) -> dict:
    """``csi`` (nodes, T, 52) complex, at least ~20 s of a resting person.

    Returns breaths and beats per minute, ``None`` when the quality is too low.
    """
    cfg = cfg or VitalsConfig()
    amp = np.abs(csi).astype(np.float64)
    nodes, t, k = amp.shape
    x = amp.transpose(1, 0, 2).reshape(t, nodes * k)
    x = x - x.mean(axis=0)
    x = x[:, x.std(axis=0) > 1e-9]
    if t < fs * 15 or x.shape[1] == 0:
        return {"breath_bpm": None, "breath_q": 0.0, "heart_bpm": None, "heart_q": 0.0}

    breath = _merged(x, BREATH_BAND, fs, cfg.top_subcarriers)
    fb, qb = _peak(breath, BREATH_BAND, fs)
    harmonics = [fb * h for h in range(2, 9)] if qb >= cfg.breath_min_quality else []
    heart = _merged(x, HEART_BAND, fs, cfg.top_subcarriers)
    fh, qh = _peak(heart, HEART_BAND, fs, exclude=harmonics)
    return {
        "breath_bpm": round(fb * 60, 1) if qb >= cfg.breath_min_quality else None,
        "breath_q": round(qb, 1),
        "heart_bpm": round(fh * 60, 1) if qh >= cfg.heart_min_quality else None,
        "heart_q": round(qh, 1),
    }
