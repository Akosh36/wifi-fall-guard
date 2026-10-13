from fastapi.testclient import TestClient

from wfg.config import load_settings
from wfg.inference.police import PoliceConfig, PoliceEscalation
from wfg.server.app import create_app
from wfg.server.notifier import CALL_BUTTONS, format_event


def run(p, states, start=0.0, step=5.0, nodes=3):
    events, t = [], start
    for s in states:
        events += p.update(s, t, nodes)
        t += step
    return [e["type"] for e in events], events


def test_intrusion_asks_the_owner_at_once():
    p = PoliceEscalation(PoliceConfig())
    types, ev = run(p, ["armed", "intrusion"])
    assert types == ["police_ask"] and ev[0]["number"] == "102"
    assert "102" in format_event(ev[0]) and CALL_BUTTONS["police_ask"][0][0]["callback_data"] == "pol:yes"


def test_owner_says_it_is_them():
    p = PoliceEscalation(PoliceConfig())
    run(p, ["intrusion"])
    assert [e["type"] for e in p.answer("Akosh", False, 10)] == ["police_cancelled"]
    assert run(p, ["intrusion"] * 60, start=15)[0] == []  # same intrusion: not asked again


def test_disarming_cancels():
    p = PoliceEscalation(PoliceConfig())
    run(p, ["intrusion"])
    assert run(p, ["off"], start=5)[0] == ["police_cancelled"]


def test_sustained_movement_counts_down_and_calls():
    p = PoliceEscalation(PoliceConfig(sustained_seconds=60, cancel_seconds=30, no_answer_seconds=0))
    types, ev = run(p, ["intrusion"] * 20)          # 0..95 s
    assert types == ["police_ask", "police_countdown", "police_call"]
    assert ev[-1]["by"] == "avtomatik" and p.state == "called"


def test_movement_that_stops_is_never_called_without_a_person():
    p = PoliceEscalation(PoliceConfig(sustained_seconds=60, no_answer_seconds=180))
    types, _ = run(p, ["intrusion"] * 4 + ["armed"] * 100)
    assert types == ["police_ask"] and p.state == "asking"


def test_no_answer_while_moving_calls_and_offline_boards_do_not_auto_call():
    p = PoliceEscalation(PoliceConfig(auto_call=True, sustained_seconds=60, no_answer_seconds=180))
    types, ev = run(p, ["intrusion"] * 40, nodes=1)  # sensors cannot vouch: no countdown
    assert types == ["police_ask", "police_call"] and ev[-1]["by"] == "javob bo'lmadi"


def test_yes_calls_and_approvals():
    p = PoliceEscalation(PoliceConfig(approvals_required=2))
    run(p, ["intrusion"])
    assert p.answer("Akosh", True, 5) == []
    assert [e["type"] for e in p.answer("Ona", True, 6)] == ["police_call"]


def test_police_api_and_disarm(tmp_path):
    s = load_settings(None)
    from wfg.train.quick import train_sim_classic
    train_sim_classic(tmp_path / "m.npz", rooms=("demo",), clips_per_class=5, stream_segments=4)
    s.update(model=str(tmp_path / "m.npz"), db=str(tmp_path / "db.sqlite3"))
    with TestClient(create_app(s, autostart=False)) as client:
        rt = client.app.state.rt
        assert client.get("/api/status").json()["police"]["state"] == "idle"
        rt.police.update("intrusion", 0.0)
        assert client.post("/api/police", json={"call": True, "who": "Akosh"}).json()["state"] == "called"
        rt.police.update("armed", 1.0)
        assert rt._command("cancel", "Telegram: Akosh") == "Hozir ochiq savol yo'q."
        rt.security.arm(0.0)
        client.post("/api/security", json={"armed": False})
        assert client.get("/api/police").json()["state"] == "idle"
        types = [e["type"] for e in client.get("/api/events").json()]
        assert "police_call" in types and "police_cancelled" in types
