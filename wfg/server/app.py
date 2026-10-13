"""FastAPI service: runs the CSI source, the inference engine, stores events,
sends Telegram alerts and serves the live dashboard."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from wfg.collector.hub import CSIHub
from wfg.collector.sources import SimSource, UDPSource
from wfg.config import load_settings
from wfg.inference.engine import Engine
from wfg.inference.events import DetectorConfig
from wfg.inference.predictor import load_predictor
from wfg.server.db import Store
from wfg.server.notifier import ACTIVITY_UZ, TelegramNotifier

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
STATE_UZ = {"monitoring": "Kuzatuv", "fall_suspected": "Yiqilish gumoni", "alert": "XAVF",
            "waiting_for_nodes": "Platalar kutilmoqda", "starting": "Ishga tushmoqda"}


class Runtime:
    """Everything the API needs, created once per app."""

    def __init__(self, settings: dict, autostart_engine: bool = True):
        self.settings = settings
        self.hub = CSIHub(settings["nodes"], fs=settings["fs"])
        model_path = Path(settings["model"])
        if not model_path.exists():
            if model_path.suffix != ".npz":
                raise FileNotFoundError(f"model not found: {model_path}")
            log.warning("model %s not found, training the baseline on simulated data", model_path)
            from wfg.train.quick import train_sim_classic
            train_sim_classic(model_path)
        self.predictor = load_predictor(model_path)
        self.store = Store(settings["db"])
        self.history: deque = deque(maxlen=1200)  # 10 minutes at 0.5 s hop
        tg = settings["telegram"]
        self.notifier = TelegramNotifier(tg.get("token") or None, self.store, tg.get("chat_ids"),
                                         status_text=self.status_text)
        if settings["source"] == "udp":
            self.source = UDPSource(self.hub, settings["udp"]["host"], settings["udp"]["port"])
        else:
            sim = settings["sim"]
            self.source = SimSource(self.hub, room=sim["room"], speed=sim["speed"], seed=sim["seed"],
                                    fs=settings["fs"], n_nodes=len(settings["nodes"]))
        self.engine = Engine(self.hub, self.predictor, settings["hop_seconds"],
                             DetectorConfig(**settings["detector"]), on_update=self._on_update,
                             on_event=self._on_event)
        self.autostart_engine = autostart_engine

    def start(self):
        self.source.start()
        if self.autostart_engine:
            self.engine.start()
        self.notifier.start_polling()

    def stop(self):
        self.engine.stop()
        self.source.stop()
        self.notifier.stop()

    def _on_update(self, latest: dict):
        self.history.append({"t": latest["t"], "activity": latest["activity"], "state": latest["state"],
                             "fall": latest["probs"].get("fall", 0.0), "motion": latest["motion"],
                             "truth": getattr(self.source, "truth", None)})

    def _on_event(self, ev: dict):
        ev = {**ev, "id": self.store.add_event(ev)}
        self.notifier.notify(ev)

    def status(self) -> dict:
        latest = dict(self.engine.latest)
        return {**latest, "state_uz": STATE_UZ.get(latest.get("state"), latest.get("state")),
                "activity_uz": ACTIVITY_UZ.get(latest.get("activity"), latest.get("activity")),
                "nodes": self.hub.stats(), "source": self.settings["source"],
                "truth": getattr(self.source, "truth", None), "classes": self.predictor.classes,
                "fall_since": self.engine.detector.suspected_at,
                "telegram": {"enabled": self.notifier.enabled, "recipients": len(self.notifier.recipients())},
                "server_time": time.time()}

    def status_text(self) -> str:
        s = self.status()
        online = sum(1 for n in s["nodes"] if n["online"])
        return (f"Holat: {s['state_uz']}\nFaoliyat: {s['activity_uz']}\n"
                f"Platalar: {online}/{len(s['nodes'])} onlayn")


def create_app(settings: dict | None = None, config_path: str | None = None, autostart: bool = True) -> FastAPI:
    settings = settings or load_settings(config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        rt = Runtime(settings)
        app.state.rt = rt
        if autostart:
            rt.start()
        yield
        rt.stop()

    app = FastAPI(title="WiFi Fall Guard", version="0.1.0", lifespan=lifespan)
    # the Android app loads its page from its own assets and calls this API across origins
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.mount("/app", StaticFiles(directory=STATIC / "app", html=True), name="app")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/status")
    def status():
        return app.state.rt.status()

    @app.get("/api/room")
    def room():
        return {**settings["room"], "nodes": settings["nodes"]}

    @app.get("/api/history")
    def history(seconds: float = 300):
        cutoff = time.time() - seconds
        return [h for h in list(app.state.rt.history) if h["t"] >= cutoff]

    @app.get("/api/events")
    def events(limit: int = 50):
        return app.state.rt.store.events(limit)

    @app.post("/api/ack")
    def ack():
        return {"events": app.state.rt.engine.acknowledge()}

    @app.post("/api/test-alert")
    def test_alert():
        from wfg.server.notifier import MESSAGES
        n = app.state.rt.notifier.send(MESSAGES["test"])
        return {"sent": n, "telegram_enabled": app.state.rt.notifier.enabled}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(app.state.rt.status())
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    return app
