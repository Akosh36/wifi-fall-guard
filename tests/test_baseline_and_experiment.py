import numpy as np

from wfg import CLASSES
from wfg.baseline.classic import ClassicModel
from wfg.csi.simulator import simulate_dataset
from wfg.data.dataset import build_arrays, few_shot_split, leave_one_out, load_records, save_record
from wfg.train.experiment import ExperimentConfig, run
from wfg.train.metrics import report


def test_classic_learns_in_one_room(tmp_path):
    recs = simulate_dataset(["r1"], clips_per_class=12, seed=0)
    x, y, _, _ = build_arrays(recs, "classic")
    m = ClassicModel(epochs=300).fit(x[::2], y[::2])
    acc = (m.predict_proba_features(x[1::2]).argmax(1) == y[1::2]).mean()
    assert acc > 0.6
    m.save(tmp_path / "m.npz")
    m2 = ClassicModel.load(tmp_path / "m.npz")
    np.testing.assert_allclose(m2.predict_proba_features(x[:3]), m.predict_proba_features(x[:3]))


def test_record_io(tmp_path, room, rng):
    from wfg.csi.simulator import simulate_clip
    save_record(tmp_path / "r" / "s" / "fall_00.npz", simulate_clip("fall", room, rng=rng), "fall", "r", "s", 100.0)
    recs = load_records(tmp_path)
    assert len(recs) == 1 and recs[0]["label"] == "fall" and recs[0]["csi"].shape == (3, 400, 52)


def test_splits():
    rooms = np.array(["a", "a", "b", "b", "c", "c"])
    folds = list(leave_one_out(rooms))
    assert [f[0] for f in folds] == ["a", "b", "c"]
    y = np.array([0, 1, 0, 1, 0, 1])
    sup, query = few_shot_split(np.arange(6), y, 1, np.random.default_rng(0))
    assert len(sup) == 2 and len(np.intersect1d(sup, query)) == 0


def test_metrics_fall_scores():
    fall = CLASSES.index("fall")
    r = report(np.array([fall, fall, 0, 0]), np.array([fall, 0, fall, 0]))
    assert r["fall_recall"] == 0.5 and r["fall_false_alarm_rate"] == 0.5


def test_experiment_runs_end_to_end(tmp_path):
    recs = simulate_dataset(["r1", "r2"], clips_per_class=6, seed=0)
    res = run(recs, ExperimentConfig(methods=["classic", "classic+restd"], shots=[0, 2]), tmp_path, log=lambda *_: None)
    assert (tmp_path / "results.md").exists()
    settings = {(r["setting"], r["method"], r["shots"]) for r in res["summary"]}
    assert ("cross-domain", "classic+restd", 2) in settings and ("in-room", "classic", 0) in settings
