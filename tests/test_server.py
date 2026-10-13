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
        assert {"location", "vitals", "security"} <= set(status)
        assert client.post("/api/security", json={"armed": True}).json()["state"] == "arming"
        assert client.get("/api/security").json()["armed"] is True
        assert client.post("/api/security", json={"armed": False}).json()["state"] == "off"
        types = [e["type"] for e in client.get("/api/events").json()]
        assert "armed" in types and "disarmed" in types
        rows = client.get("/api/history", params={"since": 0}).json()
        assert rows and rows[0]["t"] <= rows[-1]["t"] and "security" in rows[0]


def test_api_token(tmp_path):
    s = load_settings(None)
    from wfg.train.quick import train_sim_classic
    train_sim_classic(tmp_path / "m.npz", rooms=("demo",), clips_per_class=5, stream_segments=4)
    s.update(model=str(tmp_path / "m.npz"), db=str(tmp_path / "db.sqlite3"))
    s["auth"]["token"] = "secret"
    with TestClient(create_app(s, autostart=False)) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/status").status_code == 401
        assert client.get("/api/status", params={"token": "secret"}).status_code == 200
        assert client.get("/api/status", headers={"Authorization": "Bearer secret"}).status_code == 200
        import pytest
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws") as ws:
                ws.receive_json()


def test_telegram_subscribe_flow(tmp_path):
    store = Store(":memory:")
    n = TelegramNotifier(None, store)
    n.handle_update({"message": {"text": "/start", "chat": {"id": 42, "first_name": "Ona"}}})
    assert store.subscribers() == ["42"]
    n.send(format_event({"type": "alert", "t": 0, "prob": 0.9, "after_s": 20}))
    assert n.sent[-1][0] == "42" and "DIQQAT" in n.sent[-1][1]
    n.handle_update({"message": {"text": "/stop", "chat": {"id": 42}}})
    assert store.subscribers() == []
