"""Runtime settings: defaults <- YAML file <- environment variables (WFG_*)."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

DEFAULTS = {
    "source": "sim",  # "udp" for real ESP32 nodes, "sim" for the simulator
    "udp": {"host": "0.0.0.0", "port": 5500},
    "nodes": [0, 1, 2],
    "fs": 100.0,
    "model": "models/classic_sim.npz",
    "hop_seconds": 0.5,
    "detector": {
        "fall_threshold": 0.4,
        "confirm_windows": 2,
        "inactivity_seconds": 20.0,
        "recovery_threshold": 0.6,
        "recovery_windows": 3,
    },
    "sim": {"room": "demo", "speed": 1.0, "seed": 0},
    "db": "data/wfg.sqlite3",
    "telegram": {"token": "", "chat_ids": []},
    "http": {"host": "0.0.0.0", "port": 8000},
    "auth": {"token": ""},  # set when the server is reachable from outside the home network
    "security": {"exit_delay": 30.0, "confirm_windows": 3, "quiet_seconds": 60.0},
    "history_days": 7,
    # Room layout for the 3D view (metres; x = width, y = depth, z = height).
    "room": {
        "name": "Xona",
        "size": [4.0, 3.5, 2.7],
        "tx": [0.3, 0.3, 1.2],
        "rx": {"0": [3.7, 0.4, 1.0], "1": [3.7, 3.1, 1.0], "2": [0.3, 3.1, 1.0]},
        "furniture": [
            {"kind": "bed", "pos": [3.0, 2.4], "size": [1.0, 2.0], "rot": 0},
            {"kind": "chair", "pos": [0.9, 1.0], "size": [0.5, 0.5], "rot": 45},
            {"kind": "table", "pos": [0.9, 1.7], "size": [0.9, 0.6], "rot": 0},
        ],
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_settings(path: str | Path | None = None) -> dict:
    s = copy.deepcopy(DEFAULTS)
    if path and Path(path).exists():
        s = _merge(s, yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    env = os.environ
    if env.get("WFG_SOURCE"):
        s["source"] = env["WFG_SOURCE"]
    if env.get("WFG_MODEL"):
        s["model"] = env["WFG_MODEL"]
    if env.get("WFG_TELEGRAM_TOKEN"):
        s["telegram"]["token"] = env["WFG_TELEGRAM_TOKEN"]
    if env.get("WFG_TELEGRAM_CHAT_IDS"):
        s["telegram"]["chat_ids"] = [c.strip() for c in env["WFG_TELEGRAM_CHAT_IDS"].split(",") if c.strip()]
    if env.get("WFG_TOKEN"):
        s["auth"]["token"] = env["WFG_TOKEN"]
    if env.get("WFG_UDP_PORT"):
        s["udp"]["port"] = int(env["WFG_UDP_PORT"])
    return s
