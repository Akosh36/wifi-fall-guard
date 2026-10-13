from fastapi.testclient import TestClient

from wfg.config import load_settings
from wfg.inference.escalation import Escalation, EscalationConfig
from wfg.server.app import create_app
from wfg.server.db import Store
from wfg.server.notifier import CALL_BUTTONS, TelegramNotifier, format_event


def vit(t, heart=None, breath=15.0):
    return {"t": t, "heart_bpm": heart, "breath_bpm": breath}


def run(esc, until, state="alert", heart=None, breath=15.0, start=0.0, nodes=3):
    """Step the episode every 5 s with the same vital signs; returns all events."""
    events, t = [], start
    while t <= until:
        events += esc.update(state, t, vit(t, heart, breath), nodes, fall_since=0.0)
        t += 5
    return events


def types(events):
    return [e["type"] for e in events]


def test_getting_up_within_observation_is_not_an_emergency():
    esc = Escalation(EscalationConfig())
    assert run(esc, 60) == []
    assert esc.state == "observing"
    assert esc.update("monitoring", 65) == []          # got up: the detector already said "recovered"
    assert esc.state == "idle" and esc.timeline[-1]["kind"] == "resolved"


def test_abnormal_heart_rate_calls_after_countdown():
    esc = Escalation(EscalationConfig(cancel_seconds=30))
    ev = run(esc, 180, heart=150)
    assert types(ev) == ["emergency"] and "yurak" in ev[0]["reason"]
    assert esc.state == "countdown"
    ev = run(esc, 215, heart=150, start=185)
    assert types(ev) == ["emergency_call"] and ev[0]["by"] == "avtomatik" and ev[0]["number"] == "103"
    assert esc.state == "called"


def test_countdown_can_be_cancelled():
    esc = Escalation(EscalationConfig())
    run(esc, 180, heart=30)
    ev = esc.answer("Akosh", False, 190)
    assert types(ev) == ["emergency_cancelled"] and esc.state == "idle"
    assert run(esc, 400, heart=30, start=195) == []      # still down: no new episode until the person is up


def test_normal_vitals_ask_the_owner():
    esc = Escalation(EscalationConfig(approvals_required=2))
    ev = run(esc, 180, heart=72)
    assert types(ev) == ["ask_owner"] and ev[0]["verdict"] == "normal"
    assert esc.answer("Akosh", True, 190) == []           # 1 of 2 approvals
    ev = esc.answer("Telegram: Ona", True, 195)
    assert types(ev) == ["emergency_call"] and ev[0]["by"] == "Telegram: Ona"


def test_one_no_closes_the_question():
    esc = Escalation(EscalationConfig())
    run(esc, 180, heart=72)
    assert types(esc.answer("Akosh", False, 190)) == ["emergency_cancelled"]


def test_unknown_heart_rate_never_calls_by_itself():
    esc = Escalation(EscalationConfig(no_answer_seconds=0))
    ev = run(esc, 1000, heart=None, breath=None)
    assert types(ev) == ["ask_owner"] and ev[0]["verdict"] == "unknown"


def test_no_answer_calls_after_timeout():
    esc = Escalation(EscalationConfig(no_answer_seconds=300))
    ev = run(esc, 500, heart=70)
    assert types(ev) == ["ask_owner", "emergency_call"] and ev[1]["by"] == "javob bo'lmadi"


def test_vitals_turning_abnormal_while_waiting_start_the_countdown():
    esc = Escalation(EscalationConfig())
    run(esc, 180, heart=70)
    ev = run(esc, 200, heart=160, start=185)
    assert types(ev) == ["emergency"]


def test_single_abnormal_reading_and_offline_boards_do_not_auto_call():
    esc = Escalation(EscalationConfig())
    ev = []
    for t in range(0, 185, 5):
        ev += esc.update("alert", t, vit(t, 150 if t == 100 else 70), 3, fall_since=0.0)
    assert types(ev) == ["ask_owner"]                      # one outlier is not enough
    esc = Escalation(EscalationConfig())
    assert types(run(esc, 180, heart=150, nodes=1)) == ["ask_owner"]  # sensors cannot vouch for the reading


def test_auto_call_off_always_asks():
    esc = Escalation(EscalationConfig(auto_call=False))
    assert types(run(esc, 180, heart=150)) == ["ask_owner"]


def test_messages_and_buttons():
    esc = Escalation(EscalationConfig(address="Toshkent, Chilonzor 5"))
    ev = run(esc, 180, heart=150)[0]
    assert "103" in format_event(ev) and "XAVFLI" in format_event(ev)
    call = esc.answer("Akosh", True, 190)[0]
    assert "Chilonzor" in format_event(call) and "Akosh" in format_event(call)
    assert CALL_BUTTONS["ask_owner"][0][0]["callback_data"] == "esc:yes"


def test_telegram_buttons_and_commands(tmp_path):
    calls = []
    n = TelegramNotifier(None, Store(tmp_path / "db.sqlite3"), chat_ids=["1"],
                         on_command=lambda name, who: calls.append((name, who)) or "ok")
    n.handle_update({"callback_query": {"id": "q", "data": "esc:yes", "from": {"id": 1, "first_name": "Akosh"},
                                        "message": {"chat": {"id": 1}}}})
    n.handle_update({"callback_query": {"id": "q", "data": "esc:yes", "from": {"id": 2}, "message": {"chat": {"id": 2}}}})
    n.handle_update({"message": {"text": "/cancel", "chat": {"id": 1, "first_name": "Akosh"}}})
    assert calls == [("call", "Telegram: Akosh"), ("cancel", "Telegram: Akosh")]


def test_escalation_api(tmp_path):
    s = load_settings(None)
    from wfg.train.quick import train_sim_classic
    train_sim_classic(tmp_path / "m.npz", rooms=("demo",), clips_per_class=5, stream_segments=4)
    s.update(model=str(tmp_path / "m.npz"), db=str(tmp_path / "db.sqlite3"))
    with TestClient(create_app(s, autostart=False)) as client:
        rt = client.app.state.rt
        assert client.get("/api/status").json()["escalation"]["state"] == "idle"
        run(rt.escalation, 180, heart=72)
        snap = client.post("/api/escalation", json={"call": True, "who": "Akosh"}).json()
        assert snap["state"] == "called" and snap["called_by"] == "Akosh"
        assert "emergency_call" in [e["type"] for e in client.get("/api/events").json()]
        assert client.post("/api/ack").status_code == 200
        assert client.get("/api/escalation").json()["state"] == "idle"
        assert client.get("/api/escalation/snapshot").status_code == 404


def test_six_boards_and_one_offline(tmp_path):
    """4-6 boards: the config loads, and inference goes on with one board silent."""
    import numpy as np

    from wfg.collector.hub import CSIHub
    from wfg.csi.packet import CSIPacket
    s = load_settings("configs/room_6nodes.yaml")
    assert len(s["nodes"]) == 6 and len(s["room"]["rx"]) == 6
    hub = CSIHub(s["nodes"], fs=100.0)
    for i in range(500):
        for nid in range(6):
            if nid == 3 and i > 100:
                continue  # board 3 dies after 1 s
            hub.ingest(CSIPacket(node_id=nid, seq=i, esp_time_us=i * 10000, rssi=-50, noise_floor=-90, channel=6,
                                 csi=np.ones(52, np.complex64), host_time=1000 + i / 100))
    assert hub._latest_time(False) < 1001.1           # the strict window is stuck at the dead board's last packet
    assert hub._latest_time(True) > 1004.9
    assert hub.window(1.0, partial=True).shape == (5, 100, 52)
