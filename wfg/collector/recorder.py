"""Guided dataset recording: prompts the volunteer, records each repetition as one clip.

Example (one volunteer, one room, following the protocol file)::

    wfg record --room xona1_gisht --subject s03 --protocol configs/protocol.yaml

Every clip is saved as ``data/raw/<room>/<subject>/<label>_<NN>.npz`` together
with a ``session.json`` describing the hardware placement.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import yaml

from wfg import CLASSES
from wfg.collector.hub import CSIHub
from wfg.data.dataset import save_record


def _beep() -> None:
    sys.stdout.write("\a")
    sys.stdout.flush()


def record_clip(hub: CSIHub, seconds: float, settle: float = 0.3) -> "np.ndarray | None":  # noqa: F821
    """Wait ``seconds`` and return the aligned window that covers them."""
    time.sleep(seconds + settle)
    return hub.window(seconds)


def run_protocol(hub: CSIHub, out_dir: str | Path, room: str, subject: str, steps: list[dict],
                 countdown: int = 3, notes: str = "", ask=input) -> list[Path]:
    """``steps`` items: ``{"label": "fall", "reps": 10, "seconds": 5, "say": "..."}``."""
    out = Path(out_dir) / room / subject
    out.mkdir(parents=True, exist_ok=True)
    (out / "session.json").write_text(json.dumps({
        "room": room, "subject": subject, "notes": notes, "nodes": hub.node_ids(),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": steps}, ensure_ascii=False, indent=2))
    saved: list[Path] = []
    for step in steps:
        label = step["label"]
        if label not in CLASSES:
            raise ValueError(f"unknown label {label!r}; allowed: {CLASSES}")
        existing = len(list(out.glob(f"{label}_*.npz")))
        for rep in range(step.get("reps", 5)):
            print(f"\n[{label}] {rep + 1}/{step.get('reps', 5)}  {step.get('say', '')}")
            ans = ask("  Enter = boshlash, s = o'tkazib yuborish, q = chiqish: ").strip().lower()
            if ans == "q":
                return saved
            if ans == "s":
                continue
            for i in range(countdown, 0, -1):
                print(f"  {i}...", flush=True)
                time.sleep(1)
            _beep()
            print("  YOZILMOQDA", flush=True)
            csi = record_clip(hub, float(step.get("seconds", 5)))
            _beep()
            if csi is None:
                print("  XATO: barcha platalardan ma'lumot kelmadi. Ulanishni tekshiring.")
                continue
            path = save_record(out / f"{label}_{existing + rep:02d}.npz", csi, label, room, subject,
                               hub.fs, {"recorded": time.time()})
            saved.append(path)
            print(f"  saqlandi: {path}")
    return saved


def load_protocol(path: str | Path) -> list[dict]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["steps"]
