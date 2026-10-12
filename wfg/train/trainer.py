"""Training loops for the deep models and the cross-room adaptation methods.

Methods (``TrainConfig.method``):

* ``source``  train on the source rooms only (lower bound)
* ``mmd``     + MMD between source and unlabelled target-room features
* ``coral``   + CORAL between source and unlabelled target-room features
* ``dann``    + adversarial domain discriminator (gradient reversal)

Few-shot calibration in the new room (``k`` labelled clips per class):

* :func:`finetune`        fine-tune on the support set mixed with source data
* :func:`knn_mmd_adapt`   KNN-MMD style: pseudo-label target clips with a KNN over
  the support set, then class-conditional MMD; the support set is used for
  early stopping. Re-implemented from the idea in Zhao et al., arXiv:2412.04783.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from wfg.adapt.losses import DomainDiscriminator, class_conditional_mmd, coral, mmd
from wfg.models.nets import FallNet


@dataclass
class TrainConfig:
    method: str = "source"
    epochs: int = 40
    batch_size: int = 32
    lr: float = 1e-3
    weight_decay: float = 1e-4
    lambda_da: float = 0.5
    finetune_epochs: int = 40
    finetune_lr: float = 3e-4
    knn_k: int = 3
    knn_conf: float = 0.67
    seed: int = 0
    device: str = "cpu"
    verbose: bool = False


def _t(x, device, dtype=torch.float32):
    return torch.as_tensor(x, dtype=dtype, device=device)


def _batches(n: int, bs: int, rng: np.random.Generator):
    idx = rng.permutation(n)
    for i in range(0, n, bs):
        yield idx[i:i + bs]


def _class_weights(y: np.ndarray, k: int, device) -> torch.Tensor:
    counts = np.bincount(y, minlength=k).astype(np.float32)
    w = len(y) / (k * np.maximum(counts, 1))
    return _t(w, device)


@torch.no_grad()
def predict_proba(model: FallNet, x: np.ndarray, device: str = "cpu", bs: int = 128) -> np.ndarray:
    model.eval()
    out = [F.softmax(model(_t(x[i:i + bs], device)), dim=1).cpu().numpy() for i in range(0, len(x), bs)]
    return np.concatenate(out) if out else np.zeros((0, model.head.out_features))


@torch.no_grad()
def embed(model: FallNet, x: np.ndarray, device: str = "cpu", bs: int = 128) -> np.ndarray:
    model.eval()
    return np.concatenate([model.features(_t(x[i:i + bs], device)).cpu().numpy() for i in range(0, len(x), bs)])


def train(model: FallNet, xs: np.ndarray, ys: np.ndarray, cfg: TrainConfig,
          xt: np.ndarray | None = None) -> FallNet:
    """Train on labelled source clips; ``xt`` are unlabelled target-room clips for mmd/coral/dann."""
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)
    dev = cfg.device
    model.to(dev)
    k = model.head.out_features
    disc = DomainDiscriminator(model.encoder.dim).to(dev) if cfg.method == "dann" else None
    params = list(model.parameters()) + (list(disc.parameters()) if disc else [])
    opt = torch.optim.AdamW(params, lr=cfg.lr, weight_decay=cfg.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(cfg.epochs, 1))
    cw = _class_weights(ys, k, dev)
    use_target = cfg.method in ("mmd", "coral", "dann") and xt is not None and len(xt) > 1
    steps_per_epoch = math.ceil(len(xs) / cfg.batch_size)

    for epoch in range(cfg.epochs):
        model.train()
        total = 0.0
        for step, b in enumerate(_batches(len(xs), cfg.batch_size, rng)):
            x, y = _t(xs[b], dev), _t(ys[b], dev, torch.long)
            if use_target:
                tb = rng.choice(len(xt), size=min(len(b), len(xt)), replace=False)
                f_all = model.features(torch.cat([x, _t(xt[tb], dev)]))
                fs, ft = f_all[: len(b)], f_all[len(b):]
            else:
                fs = model.features(x)
            loss = F.cross_entropy(model.head(fs), y, weight=cw)
            if use_target:
                progress = (epoch * steps_per_epoch + step) / max(cfg.epochs * steps_per_epoch, 1)
                ramp = 2 / (1 + math.exp(-10 * progress)) - 1  # standard DANN schedule 0 -> 1
                if cfg.method == "mmd":
                    loss = loss + cfg.lambda_da * ramp * mmd(fs, ft)
                elif cfg.method == "coral":
                    loss = loss + cfg.lambda_da * ramp * coral(fs, ft)
                elif cfg.method == "dann":
                    logits = disc(torch.cat([fs, ft]), alpha=ramp)
                    dom = torch.cat([torch.zeros(len(fs)), torch.ones(len(ft))]).to(dev)
                    loss = loss + cfg.lambda_da * F.binary_cross_entropy_with_logits(logits, dom)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss)
        sched.step()
        if cfg.verbose:
            print(f"epoch {epoch + 1}/{cfg.epochs} loss {total / steps_per_epoch:.4f}")
    model.eval()
    return model


def finetune(model: FallNet, x_sup: np.ndarray, y_sup: np.ndarray, cfg: TrainConfig,
             xs: np.ndarray | None = None, ys: np.ndarray | None = None) -> FallNet:
    """Calibrate a trained model on a few labelled clips from the new room.

    Each step mixes the support set with an equal number of source clips so
    the model does not forget the source rooms after a handful of examples.
    """
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)
    dev = cfg.device
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.finetune_lr, weight_decay=cfg.weight_decay)
    for _ in range(cfg.finetune_epochs):
        model.train()
        x, y = x_sup, y_sup
        if xs is not None and len(xs):
            sb = rng.choice(len(xs), size=min(len(xs), max(len(x_sup), cfg.batch_size - len(x_sup))), replace=False)
            x, y = np.concatenate([x_sup, xs[sb]]), np.concatenate([y_sup, ys[sb]])
        w = torch.ones(len(y), device=dev)
        w[: len(y_sup)] = 2.0  # target-room clips count double
        loss = (F.cross_entropy(model(_t(x, dev)), _t(y, dev, torch.long), reduction="none") * w).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
    model.eval()
    return model


def knn_pseudo_labels(f_sup: np.ndarray, y_sup: np.ndarray, f_unl: np.ndarray, k: int, conf: float):
    """Label unlabelled target clips by majority vote of their ``k`` nearest support clips (cosine)."""
    a = f_sup / (np.linalg.norm(f_sup, axis=1, keepdims=True) + 1e-8)
    b = f_unl / (np.linalg.norm(f_unl, axis=1, keepdims=True) + 1e-8)
    sim = b @ a.T
    k = min(k, len(f_sup))
    nn_idx = np.argsort(-sim, axis=1)[:, :k]
    votes = y_sup[nn_idx]
    labels, share = [], []
    for row in votes:
        counts = np.bincount(row)
        labels.append(counts.argmax())
        share.append(counts.max() / len(row))
    labels, share = np.asarray(labels), np.asarray(share)
    keep = share >= conf
    return np.where(keep)[0], labels[keep]


def knn_mmd_adapt(model: FallNet, xs: np.ndarray, ys: np.ndarray, x_sup: np.ndarray, y_sup: np.ndarray,
                  x_unl: np.ndarray, cfg: TrainConfig, rounds: int = 3) -> FallNet:
    """Few-shot cross-room adaptation in the spirit of KNN-MMD (local distribution alignment)."""
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)
    dev = cfg.device
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.finetune_lr, weight_decay=cfg.weight_decay)
    best_acc, best_state = -1.0, copy.deepcopy(model.state_dict())
    epochs_per_round = max(cfg.finetune_epochs // rounds, 1)
    for _ in range(rounds):
        help_idx, help_y = knn_pseudo_labels(embed(model, x_sup, dev), y_sup, embed(model, x_unl, dev),
                                             cfg.knn_k, cfg.knn_conf)
        x_help = np.concatenate([x_sup, x_unl[help_idx]])
        y_help = np.concatenate([y_sup, help_y])
        for _ in range(epochs_per_round):
            model.train()
            sb = rng.choice(len(xs), size=min(len(xs), cfg.batch_size), replace=False)
            hb = rng.choice(len(x_help), size=min(len(x_help), cfg.batch_size), replace=False)
            fs = model.features(_t(xs[sb], dev))
            ft = model.features(_t(x_help[hb], dev))
            ys_t, yh_t = _t(ys[sb], dev, torch.long), _t(y_help[hb], dev, torch.long)
            loss = (F.cross_entropy(model.head(fs), ys_t) + F.cross_entropy(model.head(ft), yh_t)
                    + cfg.lambda_da * class_conditional_mmd(fs, ys_t, ft, yh_t))
            opt.zero_grad()
            loss.backward()
            opt.step()
            # the labelled support set doubles as the validation set for early stopping
            acc = float((predict_proba(model, x_sup, dev).argmax(1) == y_sup).mean())
            if acc >= best_acc:
                best_acc, best_state = acc, copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state)
    model.eval()
    return model
