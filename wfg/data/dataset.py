"""Recorded clips on disk -> arrays for training, plus the evaluation splits used in the thesis.

A *record* is a dict ``{"csi": complex64 (nodes, T, 52), "label": str, "room": str,
"subject": str, "fs": float}``. Recorded clips are stored one per ``.npz`` file
by :mod:`wfg.collector.recorder`; simulated clips come from
:func:`wfg.csi.simulator.simulate_dataset`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import numpy as np

from wfg import CLASS_TO_ID
from wfg.dsp.features import classic_features, doppler_spectrogram, fix_length, relative_amplitude


# ------------------------------------------------------------------------------ disk I/O

def save_record(path: str | Path, csi: np.ndarray, label: str, room: str, subject: str,
                fs: float, extra: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"label": label, "room": room, "subject": subject, "fs": fs, **(extra or {})}
    np.savez_compressed(path, csi=csi.astype(np.complex64), meta=json.dumps(meta))
    return path


def load_record(path: str | Path) -> dict:
    d = np.load(path, allow_pickle=False)
    meta = json.loads(str(d["meta"]))
    return {"csi": d["csi"], **meta, "path": str(path)}


def load_records(root: str | Path) -> list[dict]:
    """All clips under ``root`` (recursively), sorted for reproducibility."""
    return [load_record(p) for p in sorted(Path(root).rglob("*.npz"))]


# ------------------------------------------------------------------------------ arrays

def build_arrays(records: list[dict], feature: str = "amp", length: int = 400):
    """Features ``X``, integer labels ``y`` and domain metadata.

    feature:
      * ``amp``     relative amplitude, (N, nodes*52, length) for 1-D CNN / Transformer
      * ``dfs``     Doppler spectrogram, (N, nodes, F, frames) for 2-D CNN
      * ``classic`` hand-crafted vector, (N, 22) for the baseline
    """
    xs, ys, rooms, subjects = [], [], [], []
    for r in records:
        if r["label"] not in CLASS_TO_ID:
            continue
        csi = fix_length(r["csi"], length)
        fs = float(r.get("fs", 100.0))
        if feature == "amp":
            rel = relative_amplitude(csi, fs)  # (nodes, T, 52)
            x = rel.transpose(0, 2, 1).reshape(-1, rel.shape[1])
        elif feature == "dfs":
            x = doppler_spectrogram(relative_amplitude(csi, fs), fs)
        elif feature == "classic":
            x = classic_features(csi, fs)
        else:
            raise ValueError(f"unknown feature {feature!r}")
        xs.append(x)
        ys.append(CLASS_TO_ID[r["label"]])
        rooms.append(str(r["room"]))
        subjects.append(str(r.get("subject", "")))
    return (np.stack(xs).astype(np.float32), np.asarray(ys, dtype=np.int64),
            np.asarray(rooms), np.asarray(subjects))


# ------------------------------------------------------------------------------ splits

def leave_one_out(domains: np.ndarray) -> Iterator[tuple[str, np.ndarray, np.ndarray]]:
    """Leave-one-room-out (or leave-one-subject-out): yields (held_out, train_idx, test_idx)."""
    for d in np.unique(domains):
        yield str(d), np.where(domains != d)[0], np.where(domains == d)[0]


def few_shot_split(idx: np.ndarray, y: np.ndarray, k: int, rng: np.random.Generator):
    """Pick ``k`` labelled calibration clips per class from ``idx``; the rest is the test set."""
    support = []
    for c in np.unique(y[idx]):
        cand = idx[y[idx] == c]
        support.extend(rng.choice(cand, size=min(k, len(cand)), replace=False).tolist())
    support = np.asarray(sorted(support), dtype=np.int64)
    query = np.setdiff1d(idx, support)
    return support, query


def in_domain_split(idx: np.ndarray, y: np.ndarray, test_frac: float, rng: np.random.Generator):
    """Stratified random split inside one domain (the 'same room' setting)."""
    train, test = [], []
    for c in np.unique(y[idx]):
        cand = rng.permutation(idx[y[idx] == c])
        n_test = max(1, int(round(len(cand) * test_frac)))
        test.extend(cand[:n_test].tolist())
        train.extend(cand[n_test:].tolist())
    return np.asarray(sorted(train)), np.asarray(sorted(test))
