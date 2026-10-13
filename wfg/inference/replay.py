"""Offline replay of simulated scenarios through the real-time pipeline (faster than real time),
and event-level scoring: were falls caught, how quickly, and how many false alarms per hour."""

from __future__ import annotations

import numpy as np

from wfg.collector.hub import CSIHub
from wfg.csi.packet import CSIPacket
from wfg.csi.simulator import DEMO_SCENARIO, Room, ScenarioStream, random_scenario
from wfg.inference.engine import Engine
from wfg.inference.events import DetectorConfig
from wfg.inference.predictor import Predictor, load_predictor


def replay(model: str | Predictor, room: str = "demo", scenario=None, fs: float = 100.0, hop: float = 0.5,
           seed: int = 0, verbose: bool = True, detector: DetectorConfig | None = None, **stream_kwargs):
    scenario = scenario or DEMO_SCENARIO
    predictor = load_predictor(model) if isinstance(model, str) else model
    hub = CSIHub([0, 1, 2], fs=fs)
    events = []
    engine = Engine(hub, predictor, hop, detector, on_event=events.append)
    stream = ScenarioStream(Room.from_seed(room), scenario, fs=fs, seed=seed, loop=False, **stream_kwargs)
    step = int(hop * fs)
    n, rows = 0, []
    while (block := stream.read(step)) is not None:
        for i in range(step):
            t = (n + i) / fs
            for node in range(3):
                hub.ingest(CSIPacket(node, n + i, int(t * 1e6), -50, -92, 6, block[node, i], host_time=t + 1e-3))
        n += step
        latest = engine.step(now=n / fs)
        if latest:
            truth = stream.truth[n - 1]
            rows.append((n / fs, truth, latest["activity"], latest["probs"]["fall"], latest["state"]))
            if verbose:
                print(f"{n / fs:6.1f}s truth={truth:6s} pred={latest['activity']:6s} "
                      f"p(fall)={latest['probs']['fall']:.2f} state={latest['state']}")
    if verbose:
        for ev in events:
            print("EVENT", ev)
    return rows, events, stream.events


def score_events(fall_onsets_s: list[float], events: list[dict], duration_s: float, max_delay: float = 6.0) -> dict:
    """Match ``fall_suspected`` events to true fall onsets (within ``max_delay`` seconds)."""
    suspected = [e["t"] for e in events if e["type"] == "fall_suspected"]
    used, delays = set(), []
    for onset in fall_onsets_s:
        hits = [i for i, t in enumerate(suspected) if i not in used and 0 <= t - onset <= max_delay]
        if hits:
            used.add(hits[0])
            delays.append(suspected[hits[0]] - onset)
    false_alarms = len(suspected) - len(used)
    return {"falls": len(fall_onsets_s), "detected": len(delays),
            "recall": len(delays) / max(len(fall_onsets_s), 1),
            "mean_delay_s": float(np.mean(delays)) if delays else None,
            "false_alarms": false_alarms, "false_alarms_per_hour": false_alarms / max(duration_s / 3600, 1e-9)}


def evaluate_streams(model: str | Predictor, rooms: list[str], scenarios_per_room: int = 5, n_segments: int = 20,
                     seed: int = 0, detector: DetectorConfig | None = None, fs: float = 100.0) -> dict:
    """Event-level evaluation over random day-in-the-life scenarios in each room."""
    predictor = load_predictor(model) if isinstance(model, str) else model
    rng = np.random.default_rng(seed)
    per_room = {}
    for room in rooms:
        onsets, events_all, duration = [], [], 0.0
        for _ in range(scenarios_per_room):
            scenario = random_scenario(rng, n_segments)
            rows, events, truth_events = replay(predictor, room, scenario, fs=fs, seed=int(rng.integers(1 << 31)),
                                                verbose=False, detector=detector)
            offset = duration
            onsets += [offset + i / fs for i, act in truth_events if act == "fall"]
            events_all += [{**e, "t": e["t"] + offset} for e in events]
            duration += rows[-1][0] if rows else 0.0
        per_room[room] = score_events(onsets, events_all, duration)
    return per_room
