"""FastAPI service: runs the CSI source, the inference engine, stores events,
sends Telegram alerts and serves the live dashboard."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from wfg.collector.hub import CSIHub
from wfg.collector.sources import SimSource, UDPSource
from wfg.config import load_settings
from wfg.geometry import RoomLayout
from wfg.inference.analytics import Analytics
from wfg.inference.engine import Engine
from wfg.inference.events import DetectorConfig
from wfg.inference.predictor import load_predictor
from wfg.inference.security import SecurityConfig, SecurityMonitor
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
            train_sim_classic(model_path, layout=RoomLayout.from_config(settings["room"], settings["nodes"]))
        self.predictor = load_predictor(model_path)
        self.store = Store(settings["db"])
        self.history: deque = deque(maxlen=1200)  # 10 minutes at 0.5 s hop
        tg = settings["telegram"]
        self.notifier = TelegramNotifier(tg.get("token") or None, self.store, tg.get("chat_ids"),
                                         status_text=self.status_text, on_command=self._command)
        self.layout = RoomLayout.from_config(settings["room"], settings["nodes"])
        if settings["source"] == "udp":
            self.source = UDPSource(self.hub, settings["udp"]["host"], settings["udp"]["port"])
        else:
            sim = settings["sim"]
            self.source = SimSource(self.hub, room=sim["room"], speed=sim["speed"], seed=sim["seed"],
                                    fs=settings["fs"], n_nodes=len(settings["nodes"]), layout=self.layout)
        self.analytics = Analytics(self.hub, self.layout)
        self.extra: dict = {"location": None, "vitals": self.analytics.vitals}
        self.security = SecurityMonitor(SecurityConfig(**settings["security"]),
                                        armed=self.store.get_setting("armed") == "1", now=time.time())
        self.retention = settings["history_days"] * 86400
        self._last_prune = 0.0
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
        now = latest["t"]
        self.extra = self.analytics.update(latest["activity"], latest["state"], now)
        present = latest["activity"] not in ("empty", "unknown")
        for ev in self.security.update(present, now, latest["motion"]):
            self._on_event(ev)
        loc, vit = self.extra["location"] or {}, self.extra["vitals"]
        row = {"t": now, "activity": latest["activity"], "state": latest["state"],
               "fall": latest["probs"].get("fall", 0.0), "motion": latest["motion"],
               "x": loc.get("x"), "y": loc.get("y"), "breath": vit.get("breath_bpm"),
               "heart": vit.get("heart_bpm"), "security": self.security.state}
        self.store.add_history(row)
        self.history.append({**row, "truth": getattr(self.source, "truth", None)})
        if now - self._last_prune > 3600:
            self._last_prune = now
            self.store.prune_history(now - self.retention)

    def _on_event(self, ev: dict):
        ev = {**ev, "id": self.store.add_event(ev)}
        self.notifier.notify(ev)

    def set_armed(self, armed: bool) -> dict:
        now = time.time()
        events = self.security.arm(now) if armed else self.security.disarm(now)
        self.store.set_setting("armed", "1" if armed else "0")
        for ev in events:
            self._on_event(ev)
        return self.security.snapshot()

    def _command(self, name: str) -> str | None:
        if name in ("arm", "disarm"):
            self.set_armed(name == "arm")
            return None  # the armed / disarmed event message goes to everyone
        return None

    def status(self) -> dict:
        latest = dict(self.engine.latest)
        return {**latest, "state_uz": STATE_UZ.get(latest.get("state"), latest.get("state")),
                "activity_uz": ACTIVITY_UZ.get(latest.get("activity"), latest.get("activity")),
                "nodes": self.hub.stats(), "source": self.settings["source"],
                "truth": getattr(self.source, "truth", None), "classes": self.predictor.classes,
                "fall_since": self.engine.detector.suspected_at,
                "location": self.extra["location"], "vitals": self.extra["vitals"],
                "security": self.security.snapshot(),
                "truth_pos": getattr(self.source, "truth_pos", None),
                "telegram": {"enabled": self.notifier.enabled, "recipients": len(self.notifier.recipients())},
                "server_time": time.time()}

    def status_text(self) -> str:
        s = self.status()
        online = sum(1 for n in s["nodes"] if n["online"])
        sec = {"off": "o'chiq", "arming": "yoqilmoqda", "armed": "yoqilgan", "intrusion": "HARAKAT ANIQLANDI"}
        return (f"Holat: {s['state_uz']}\nFaoliyat: {s['activity_uz']}\n"
                f"Qo'riqlash: {sec.get(s['security']['state'], s['security']['state'])}\n"
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
    token = settings["auth"].get("token") or ""

    def authorized(headers, query) -> bool:
        if not token:
            return True
        given = query.get("token") or headers.get("authorization", "").removeprefix("Bearer ").strip()
        return given == token

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        # with a token set (needed when the server is reachable from outside the home) the API needs it
        if request.url.path.startswith("/api/") and request.url.path != "/api/health" \
                and request.method != "OPTIONS" and not authorized(request.headers, request.query_params):
            return JSONResponse({"detail": "token kerak"}, status_code=401)
        return await call_next(request)

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
    def history(seconds: float | None = None, since: float | None = None, limit: int = 5000):
        """``seconds``: recent in-memory rows (dashboard). ``since``: stored rows after that time,
        oldest first, for clients that were offline and want to fill the gap."""
        if since is not None:
            return app.state.rt.store.history(since, limit=min(limit, 20000))
        cutoff = time.time() - (seconds or 300)
        return [h for h in list(app.state.rt.history) if h["t"] >= cutoff]

    @app.get("/api/events")
    def events(limit: int = 50, since: float | None = None):
        return app.state.rt.store.events(limit, since)

    @app.get("/api/security")
    def security_get():
        return app.state.rt.security.snapshot()

    @app.post("/api/security")
    def security_set(armed: bool = Body(..., embed=True)):
        return app.state.rt.set_armed(armed)

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
        if not authorized(websocket.headers, websocket.query_params):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(app.state.rt.status())
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    return app
