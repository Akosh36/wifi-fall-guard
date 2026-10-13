import time

from fastapi.testclient import TestClient

from wfg.config import load_settings
from wfg.server.app import create_app
from wfg.server.db import Store
from wfg.server.notifier import TelegramNotifier, format_event


def test_api_with_simulator(tmp_path):
    s = load_settings(None)
    from wfg.train.quick import train_sim_classic
    train_sim_classic(tmp_path / "m.npz", rooms=("demo",), clips_per_class=5, stream_segments=4)  # small and fast
    s.update(model=str(tmp_path / "m.npz"), db=str(tmp_path / "db.sqlite3"), hop_seconds=0.5)
    s["sim"]["speed"] = 4.0
    with TestClient(create_app(s)) as client:
        assert client.get("/api/health").json() == {"ok": True}
        assert "WiFi Fall Guard" in client.get("/").text
        deadline = time.time() + 30
        status = client.get("/api/status").json()
        while status.get("state") in ("starting", "waiting_for_nodes") and time.time() < deadline:
            time.sleep(0.5)
            status = client.get("/api/status").json()
        assert status["state"] in ("monitoring", "fall_suspected", "alert")
        assert len(status["nodes"]) == 3 and all(n["online"] for n in status["nodes"])
        assert set(status["probs"]) == set(status["classes"])
        assert client.post("/api/test-alert").json()["telegram_enabled"] is False
        assert isinstance(client.get("/api/events").json(), list)
        room = client.get("/api/room").json()
        assert len(room["size"]) == 3 and set(room["rx"]) == {"0", "1", "2"}
        assert "three" in client.get("/app/").text
        assert client.get("/app/vendor/three.module.min.js").status_code == 200
        with client.websocket_connect("/ws") as ws:
            assert "state" in ws.receive_json()


def test_telegram_subscribe_flow(tmp_path):
    store = Store(":memory:")
    n = TelegramNotifier(None, store)
    n.handle_update({"message": {"text": "/start", "chat": {"id": 42, "first_name": "Ona"}}})
    assert store.subscribers() == ["42"]
    n.send(format_event({"type": "alert", "t": 0, "prob": 0.9, "after_s": 20}))
    assert n.sent[-1][0] == "42" and "DIQQAT" in n.sent[-1][1]
    n.handle_update({"message": {"text": "/stop", "chat": {"id": 42}}})
    assert store.subscribers() == []
