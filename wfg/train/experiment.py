"""The thesis experiment: how well does fall detection transfer to a room the model never saw?

For every room R (leave-one-room-out):
  * train on all other rooms,
  * evaluate on R with 0 labelled clips from R (no calibration),
  * and with k labelled calibration clips per class from R (few-shot).
An *in-room* reference (train and test inside the same room) gives the upper bound.

Results are written as JSON (all numbers) and Markdown (tables for the thesis).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from wfg import CLASSES
from wfg.baseline.classic import ClassicModel
from wfg.data.dataset import build_arrays, few_shot_split, in_domain_split, leave_one_out
from wfg.train.metrics import report


@dataclass
class ExperimentConfig:
    methods: list[str] = field(default_factory=lambda: ["classic", "classic+restd"])
    shots: list[int] = field(default_factory=lambda: [0, 5])
    seeds: list[int] = field(default_factory=lambda: [0])
    length: int = 400
    domain: str = "room"  # or "subject"
    epochs: int = 40
    device: str = "cpu"
    in_room_test_frac: float = 0.3


# Deep method name -> (architecture, adaptation used while training). Suffix "+ft" or
# "+knnmmd" adds few-shot calibration, e.g. "cnn1d+knnmmd".
DEEP = {
    "cnn1d": ("cnn1d", "source"), "cnn1d+mmd": ("cnn1d", "mmd"), "cnn1d+coral": ("cnn1d", "coral"),
    "cnn1d+dann": ("cnn1d", "dann"), "transformer": ("transformer", "source"),
    "transformer+dann": ("transformer", "dann"), "cnn2d": ("cnn2d", "source"), "cnn2d+mmd": ("cnn2d", "mmd"),
}


def _is_adaptation(method: str) -> bool:
    if method == "classic+restd" or method.endswith(("+ft", "+knnmmd")):
        return True
    return method in DEEP and DEEP[method][1] != "source"


def _classic(method: str, X, y, train_idx, sup, query):
    tr = np.concatenate([train_idx, sup]) if len(sup) else train_idx
    m = ClassicModel().fit(X[tr], y[tr])
    stats = None
    if method == "classic+restd":
        tgt = np.concatenate([sup, query]) if len(sup) else query  # unlabelled target statistics
        stats = (X[tgt].mean(0), X[tgt].std(0) + 1e-6)
    return m.predict_proba_features(X[query], stats).argmax(1)


def _deep(method: str, feats: dict, y, train_idx, sup, query, cfg: ExperimentConfig, seed: int):
    from wfg.models.nets import build_model, feature_for
    from wfg.train.trainer import TrainConfig, finetune, knn_mmd_adapt, predict_proba, train

    base, fewshot = method, None
    for suffix in ("+ft", "+knnmmd"):
        if method.endswith(suffix):
            base, fewshot = method[: -len(suffix)], suffix[1:]
    arch, da = DEEP[base]
    X = feats[feature_for(arch)]
    tcfg = TrainConfig(method=da, epochs=cfg.epochs, seed=seed, device=cfg.device)
    model = build_model(arch, X.shape[1:], len(CLASSES))
    target_unl = np.concatenate([sup, query]) if len(sup) else query
    train_on = train_idx if fewshot else (np.concatenate([train_idx, sup]) if len(sup) else train_idx)
    train(model, X[train_on], y[train_on], tcfg, xt=X[target_unl])
    if fewshot == "ft" and len(sup):
        finetune(model, X[sup], y[sup], tcfg, X[train_idx], y[train_idx])
    elif fewshot == "knnmmd" and len(sup):
        knn_mmd_adapt(model, X[train_idx], y[train_idx], X[sup], y[sup], X[query], tcfg)
    return predict_proba(model, X[query], cfg.device).argmax(1)


def run(records: list[dict], cfg: ExperimentConfig, out_dir: str | Path, log=print) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    need = {"classic"}
    deep_methods = [m for m in cfg.methods if not m.startswith("classic")]
    if deep_methods:
        from wfg.models.nets import feature_for
        for m in deep_methods:
            base = m.replace("+ft", "").replace("+knnmmd", "")
            need.add(feature_for(DEEP[base][0]))
    feats, y, rooms, subjects = {}, None, None, None
    for f in sorted(need):
        feats[f], y, rooms, subjects = build_arrays(records, f, cfg.length)
    domains = rooms if cfg.domain == "room" else subjects
    log(f"{len(y)} clips, domains: {sorted(set(domains))}, features: {sorted(feats)}")

    rows = []
    for seed in cfg.seeds:
        rng = np.random.default_rng(seed)
        # in-room reference
        for d in np.unique(domains):
            idx = np.where(domains == d)[0]
            tr, te = in_domain_split(idx, y, cfg.in_room_test_frac, rng)
            for method in cfg.methods:
                if _is_adaptation(method):
                    continue  # adaptation methods are meaningless inside one room
                pred = (_classic(method, feats["classic"], y, tr, np.array([], int), te) if method.startswith("classic")
                        else _deep(method, feats, y, tr, np.array([], int), te, cfg, seed))
                rows.append({"setting": "in-room", "domain": d, "method": method, "shots": 0, "seed": seed,
                             **report(y[te], pred)})
                log(f"[in-room] {d} {method}: acc {rows[-1]['accuracy']:.3f} fall_f1 {rows[-1]['fall_f1']:.3f}")
        # cross-room
        for d, train_idx, test_idx in leave_one_out(domains):
            for k in cfg.shots:
                sup, query = few_shot_split(test_idx, y, k, rng) if k else (np.array([], int), test_idx)
                for method in cfg.methods:
                    if k == 0 and method.endswith(("+ft", "+knnmmd")):
                        continue
                    t0 = time.time()
                    pred = (_classic(method, feats["classic"], y, train_idx, sup, query) if method.startswith("classic")
                            else _deep(method, feats, y, train_idx, sup, query, cfg, seed))
                    rows.append({"setting": "cross-domain", "domain": d, "method": method, "shots": k, "seed": seed,
                                 "seconds": round(time.time() - t0, 1), **report(y[query], pred)})
                    log(f"[new {cfg.domain}] {d} k={k} {method}: acc {rows[-1]['accuracy']:.3f} "
                        f"fall_f1 {rows[-1]['fall_f1']:.3f}")

    summary = summarize(rows)
    result = {"config": asdict(cfg), "classes": CLASSES, "rows": rows, "summary": summary}
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    (out_dir / "results.md").write_text(to_markdown(summary, cfg))
    return result


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["setting"], r["method"], r["shots"]), []).append(r)
    out = []
    for (setting, method, shots), rs in sorted(groups.items()):
        out.append({"setting": setting, "method": method, "shots": shots, "runs": len(rs),
                    **{m: float(np.mean([r[m] for r in rs])) for m in
                       ("accuracy", "macro_f1", "fall_recall", "fall_precision", "fall_f1", "fall_false_alarm_rate")},
                    "accuracy_std": float(np.std([r["accuracy"] for r in rs]))})
    return out


def to_markdown(summary: list[dict], cfg: ExperimentConfig) -> str:
    lines = [f"# Natijalar (domain = {cfg.domain})", "",
             "| Sharoit | Usul | k (kalibrlash) | Aniqlik | Macro-F1 | Yiqilish recall | Yiqilish precision | Yolg'on signal |",
             "|---|---|---|---|---|---|---|---|"]
    for s in summary:
        setting = "Bir xonada" if s["setting"] == "in-room" else "Yangi xona"
        lines.append(f"| {setting} | {s['method']} | {s['shots']} | {s['accuracy']:.1%} ± {s['accuracy_std']:.1%} | "
                     f"{s['macro_f1']:.3f} | {s['fall_recall']:.1%} | {s['fall_precision']:.1%} | "
                     f"{s['fall_false_alarm_rate']:.1%} |")
    return "\n".join(lines) + "\n"
