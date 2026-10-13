"""Train the NumPy baseline on simulated rooms, so the demo works before any real data exists.

The "demo" room is included on purpose: it plays the role of the calibrated home
where the system is installed. Unseen rooms are what `wfg experiment` measures.
"""

from __future__ import annotations

from pathlib import Path

from wfg.baseline.classic import ClassicModel
import numpy as np

from wfg.csi.simulator import Room, simulate_dataset, stream_windows
from wfg.data.dataset import build_arrays


def train_sim_classic(path: str | Path, rooms=("demo", "sim_a", "sim_b", "sim_c", "sim_d"),
                      clips_per_class: int = 30, stream_segments: int = 60, seed: int = 0,
                      layout=None) -> ClassicModel:
    """``layout``: also train on streams where the person moves around that room plan, which
    makes each link's signal depend on where they are (what the live demo simulates)."""
    records = simulate_dataset(list(rooms), clips_per_class=clips_per_class, seed=seed)
    rng = np.random.default_rng(seed)
    for room in rooms:  # plus sliding windows over continuous scenarios, as the live engine sees them
        records += stream_windows(Room.from_seed(room), rng, n_segments=stream_segments)
        if layout is not None:
            records += stream_windows(Room.from_seed(room), rng, n_segments=stream_segments // 2, layout=layout)
    x, y, _, _ = build_arrays(records, "classic")
    model = ClassicModel().fit(x, y)
    model.save(path)
    return model


def train_classic_from_records(records: list[dict], path: str | Path) -> ClassicModel:
    x, y, _, _ = build_arrays(records, "classic")
    model = ClassicModel().fit(x, y)
    model.save(path)
    return model
