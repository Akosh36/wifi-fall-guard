"""Metrics reported in the thesis. Fall detection is also scored as a binary task,
because what matters to a family is: was the fall caught, and how often does the
phone ring for nothing."""

from __future__ import annotations

import numpy as np

from wfg import CLASSES, FALL_ID


def confusion(y_true: np.ndarray, y_pred: np.ndarray, k: int = len(CLASSES)) -> np.ndarray:
    m = np.zeros((k, k), dtype=np.int64)
    np.add.at(m, (y_true, y_pred), 1)
    return m


def report(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    cm = confusion(y_true, y_pred)
    acc = float((y_true == y_pred).mean()) if len(y_true) else 0.0
    per_class_f1 = []
    for c in range(len(CLASSES)):
        tp = cm[c, c]
        p = tp / max(cm[:, c].sum(), 1)
        r = tp / max(cm[c, :].sum(), 1)
        per_class_f1.append(0.0 if p + r == 0 else 2 * p * r / (p + r))
    present = np.unique(y_true)
    macro_f1 = float(np.mean([per_class_f1[c] for c in present])) if len(present) else 0.0

    is_fall, said_fall = y_true == FALL_ID, y_pred == FALL_ID
    tp = int((is_fall & said_fall).sum())
    fn = int((is_fall & ~said_fall).sum())
    fp = int((~is_fall & said_fall).sum())
    tn = int((~is_fall & ~said_fall).sum())
    recall = tp / max(tp + fn, 1)
    precision = tp / max(tp + fp, 1)
    return {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "fall_recall": recall,  # sensitivity: share of real falls detected
        "fall_precision": precision,
        "fall_f1": 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision),
        "fall_false_alarm_rate": fp / max(fp + tn, 1),  # share of normal clips flagged as a fall
        "n": int(len(y_true)),
        "confusion": cm.tolist(),
    }
