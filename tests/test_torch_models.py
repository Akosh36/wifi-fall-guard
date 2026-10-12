"""Deep model tests; skipped automatically where PyTorch is not installed."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from wfg import CLASSES  # noqa: E402
from wfg.adapt.losses import coral, mmd  # noqa: E402
from wfg.csi.simulator import simulate_dataset  # noqa: E402
from wfg.data.dataset import build_arrays  # noqa: E402
from wfg.models.nets import build_model, feature_for, load_checkpoint, save_checkpoint  # noqa: E402
from wfg.train.experiment import ExperimentConfig, run  # noqa: E402
from wfg.train.trainer import TrainConfig, finetune, knn_mmd_adapt, predict_proba, train  # noqa: E402


@pytest.mark.parametrize("arch", ["cnn1d", "transformer", "cnn2d"])
def test_forward_shapes(arch):
    recs = simulate_dataset(["r"], clips_per_class=1, seed=0)
    x, _, _, _ = build_arrays(recs, feature_for(arch))
    m = build_model(arch, x.shape[1:], len(CLASSES))
    assert m(torch.as_tensor(x)).shape == (len(x), len(CLASSES))


def test_losses_are_zero_for_identical_sets():
    a = torch.randn(16, 8)
    assert float(mmd(a, a)) < 1e-5 and float(coral(a, a)) < 1e-8
    assert float(mmd(a, a + 3)) > 0.1


@pytest.mark.parametrize("method", ["source", "mmd", "coral", "dann"])
def test_training_methods_run(method):
    recs = simulate_dataset(["r1", "r2"], clips_per_class=4, seed=0)
    x, y, rooms, _ = build_arrays(recs, "amp")
    m = build_model("cnn1d", x.shape[1:], len(CLASSES))
    src, tgt = rooms == "r1", rooms == "r2"
    train(m, x[src], y[src], TrainConfig(method=method, epochs=2, batch_size=8), xt=x[tgt])
    p = predict_proba(m, x[tgt])
    assert p.shape == (tgt.sum(), len(CLASSES)) and np.allclose(p.sum(1), 1, atol=1e-5)


def test_fewshot_and_checkpoint(tmp_path):
    recs = simulate_dataset(["r1", "r2"], clips_per_class=4, seed=0)
    x, y, rooms, _ = build_arrays(recs, "amp")
    src, tgt = np.where(rooms == "r1")[0], np.where(rooms == "r2")[0]
    cfg = TrainConfig(epochs=2, batch_size=8, finetune_epochs=3)
    m = build_model("cnn1d", x.shape[1:], len(CLASSES))
    train(m, x[src], y[src], cfg)
    finetune(m, x[tgt[:6]], y[tgt[:6]], cfg, x[src], y[src])
    knn_mmd_adapt(m, x[src], y[src], x[tgt[:6]], y[tgt[:6]], x[tgt[6:]], cfg)
    save_checkpoint(tmp_path / "m.pt", m, "cnn1d", x.shape[1:], CLASSES, 400, 100.0)
    m2, ck = load_checkpoint(tmp_path / "m.pt")
    np.testing.assert_allclose(predict_proba(m2, x[:2]), predict_proba(m, x[:2]), atol=1e-5)

    from wfg.inference.predictor import load_predictor
    p = load_predictor(tmp_path / "m.pt").predict(recs[0]["csi"])
    assert p.shape == (len(CLASSES),)


def test_deep_experiment_smoke(tmp_path):
    recs = simulate_dataset(["r1", "r2"], clips_per_class=3, seed=0)
    res = run(recs, ExperimentConfig(methods=["cnn1d", "cnn1d+mmd", "cnn1d+knnmmd"], shots=[0, 1], epochs=1),
              tmp_path, log=lambda *_: None)
    assert any(r["method"] == "cnn1d+knnmmd" for r in res["summary"])
