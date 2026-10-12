"""Replay the demo scenario through the real-time pipeline faster than real time.

Prints predicted vs true activity and the fall events, which is a quick way to
tune the detector settings (configs/default.yaml -> detector) before a demo.

    python scripts/replay_scenario.py --model models/classic_sim.npz --room demo
"""

import argparse

from wfg.inference.replay import replay

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/classic_sim.npz")
    ap.add_argument("--room", default="demo")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    replay(a.model, a.room, seed=a.seed)
