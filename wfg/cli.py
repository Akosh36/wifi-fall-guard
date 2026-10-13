"""Command line interface: ``wfg <command> --help``."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path


def cmd_simulate(a):
    from wfg.csi.simulator import simulate_dataset
    from wfg.data.dataset import save_record
    recs = simulate_dataset(a.rooms, clips_per_class=a.clips, duration=a.seconds, seed=a.seed)
    for i, r in enumerate(recs):
        save_record(Path(a.out) / r["room"] / r["subject"] / f"{r['label']}_{i:05d}.npz",
                    r["csi"], r["label"], r["room"], r["subject"], r["fs"], {"simulated": True})
    print(f"{len(recs)} clips written to {a.out}")


def cmd_nodes(a):
    from wfg.collector.hub import CSIHub
    from wfg.collector.sources import UDPSource
    hub = CSIHub(a.nodes or None)
    src = UDPSource(hub, port=a.port).start()
    print(f"udp://0.0.0.0:{a.port} kutilmoqda. Ctrl+C - chiqish")
    try:
        while True:
            time.sleep(2)
            rows = hub.stats()
            line = "  ".join(f"#{r['node']}: {'ON ' if r['online'] else 'OFF'} {r['rate_hz']:5.1f} Hz "
                             f"loss {r['loss']:.1%} rssi {r['rssi']}" for r in rows)
            print(line or "hali paket kelmadi", f"  bad={src.bad_packets}", flush=True)
    except KeyboardInterrupt:
        src.stop()


def cmd_record(a):
    from wfg.collector.hub import CSIHub
    from wfg.collector.recorder import load_protocol, run_protocol
    from wfg.collector.sources import SimSource, UDPSource
    hub = CSIHub(a.nodes, fs=a.fs)
    src = (SimSource(hub) if a.sim else UDPSource(hub, port=a.port)).start()
    time.sleep(1.0)
    steps = (load_protocol(a.protocol) if a.protocol else
             [{"label": a.label, "reps": a.reps, "seconds": a.seconds, "say": ""}])
    try:
        saved = run_protocol(hub, a.out, a.room, a.subject, steps, notes=a.notes)
        print(f"\n{len(saved)} ta klip saqlandi.")
    finally:
        src.stop()


def cmd_train(a):
    from wfg import CLASSES
    from wfg.data.dataset import build_arrays, load_records
    records = load_records(a.data)
    if not records:
        sys.exit(f"no .npz clips found under {a.data}")
    out = Path(a.out)
    if a.arch == "classic":
        from wfg.train.quick import train_classic_from_records
        train_classic_from_records(records, out.with_suffix(".npz"))
        print(f"saved {out.with_suffix('.npz')}")
        return
    from wfg.models.nets import build_model, feature_for, save_checkpoint
    from wfg.train.trainer import TrainConfig, train
    x, y, _, _ = build_arrays(records, feature_for(a.arch), a.length)
    model = build_model(a.arch, x.shape[1:], len(CLASSES))
    train(model, x, y, TrainConfig(epochs=a.epochs, device=a.device, verbose=True))
    save_checkpoint(out.with_suffix(".pt"), model, a.arch, x.shape[1:], CLASSES, a.length,
                    float(records[0].get("fs", 100.0)))
    print(f"saved {out.with_suffix('.pt')}")


def cmd_experiment(a):
    from wfg.data.dataset import load_records
    from wfg.train.experiment import ExperimentConfig, run
    records = load_records(a.data)
    if not records:
        sys.exit(f"no .npz clips found under {a.data}")
    cfg = ExperimentConfig(methods=a.methods, shots=a.shots, seeds=a.seeds, domain=a.domain,
                           epochs=a.epochs, device=a.device, length=a.length)
    res = run(records, cfg, a.out)
    print((Path(a.out) / "results.md").read_text())
    return res


def cmd_stream_eval(a):
    import json
    from wfg.inference.replay import evaluate_streams
    res = evaluate_streams(a.model, a.rooms, a.scenarios, a.segments, a.seed)
    print(json.dumps(res, indent=2))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=2))


def cmd_serve(a, demo: bool = False):
    import uvicorn
    from wfg.config import load_settings
    from wfg.server.app import create_app
    s = load_settings(a.config)
    if demo:
        s["source"] = "sim"
        s["sim"]["speed"] = a.speed
    if getattr(a, "source", None):
        s["source"] = a.source
    if getattr(a, "model", None):
        s["model"] = a.model
    print(f"Dashboard: http://localhost:{a.port}   3D xona: http://localhost:{a.port}/app/")
    uvicorn.run(create_app(s), host=s["http"]["host"], port=a.port, log_level="info")


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="wfg", description="WiFi Fall Guard")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="generate a simulated dataset")
    s.add_argument("--rooms", nargs="+", default=["sim_a", "sim_b", "sim_c", "sim_d"])
    s.add_argument("--clips", type=int, default=30, help="clips per class per room")
    s.add_argument("--seconds", type=float, default=4.0)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", default="data/sim")
    s.set_defaults(func=cmd_simulate)

    s = sub.add_parser("nodes", help="check that ESP32 receivers are sending CSI")
    s.add_argument("--port", type=int, default=5500)
    s.add_argument("--nodes", type=int, nargs="*")
    s.set_defaults(func=cmd_nodes)

    s = sub.add_parser("record", help="record labelled clips with real nodes")
    s.add_argument("--room", required=True)
    s.add_argument("--subject", required=True)
    s.add_argument("--protocol", help="YAML protocol, e.g. configs/protocol.yaml")
    s.add_argument("--label", default="fall")
    s.add_argument("--reps", type=int, default=10)
    s.add_argument("--seconds", type=float, default=5.0)
    s.add_argument("--nodes", type=int, nargs="+", default=[0, 1, 2])
    s.add_argument("--port", type=int, default=5500)
    s.add_argument("--fs", type=float, default=100.0)
    s.add_argument("--out", default="data/raw")
    s.add_argument("--notes", default="")
    s.add_argument("--sim", action="store_true", help="use the simulator instead of real nodes (for practice)")
    s.set_defaults(func=cmd_record)

    s = sub.add_parser("train", help="train one model on all clips and save it")
    s.add_argument("--data", required=True)
    s.add_argument("--arch", default="classic", choices=["classic", "cnn1d", "transformer", "cnn2d"])
    s.add_argument("--out", default="models/model")
    s.add_argument("--epochs", type=int, default=40)
    s.add_argument("--length", type=int, default=400)
    s.add_argument("--device", default="cpu")
    s.set_defaults(func=cmd_train)

    s = sub.add_parser("experiment", help="leave-one-room-out evaluation with few-shot calibration")
    s.add_argument("--data", required=True)
    s.add_argument("--methods", nargs="+", default=["classic", "classic+restd"])
    s.add_argument("--shots", type=int, nargs="+", default=[0, 5])
    s.add_argument("--seeds", type=int, nargs="+", default=[0])
    s.add_argument("--domain", default="room", choices=["room", "subject"])
    s.add_argument("--epochs", type=int, default=40)
    s.add_argument("--length", type=int, default=400)
    s.add_argument("--device", default="cpu")
    s.add_argument("--out", default="results/latest")
    s.set_defaults(func=cmd_experiment)

    s = sub.add_parser("stream-eval", help="event-level evaluation on simulated continuous scenarios")
    s.add_argument("--model", default="models/classic_sim.npz")
    s.add_argument("--rooms", nargs="+", default=["demo", "unseen_1", "unseen_2"])
    s.add_argument("--scenarios", type=int, default=5)
    s.add_argument("--segments", type=int, default=20)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out")
    s.set_defaults(func=cmd_stream_eval)

    for name, demo in (("serve", False), ("demo", True)):
        s = sub.add_parser(name, help="run the dashboard" + (" with the simulator" if demo else ""))
        s.add_argument("--config", default="configs/default.yaml")
        s.add_argument("--port", type=int, default=8000)
        if demo:
            s.add_argument("--speed", type=float, default=1.0)
        else:
            s.add_argument("--source", choices=["sim", "udp"])
            s.add_argument("--model")
        s.set_defaults(func=lambda a, demo=demo: cmd_serve(a, demo))

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
