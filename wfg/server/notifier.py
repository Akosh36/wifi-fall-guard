"""Alerts for relatives through a Telegram bot.

Create a bot with @BotFather, put the token in ``WFG_TELEGRAM_TOKEN``. Each
relative opens the bot and sends ``/start``; from then on they receive alerts.
``/status`` replies with the current state, ``/stop`` unsubscribes.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable

import httpx

from wfg.server.db import Store

log = logging.getLogger(__name__)

MESSAGES = {
    "fall_suspected": "⚠️ Yiqilish ehtimoli aniqlandi ({prob:.0%}). Tizim odam turib ketishini kutmoqda...",
    "alert": "🚨 DIQQAT! {time} da yiqilish aniqlandi va odam {after_s:.0f} soniyadan beri turmadi. Iltimos, darhol tekshiring!",
    "recovered": "✅ Odam turdi va yura boshladi ({after_s:.0f} soniyadan keyin). Xavf bekor qilindi.",
    "acknowledged": "👍 Ogohlantirish qabul qilindi.",
    "test": "🔔 Sinov xabari: WiFi Fall Guard ishlayapti.",
}

ACTIVITY_UZ = {"empty": "xona bo'sh", "still": "qimirlamayapti", "walk": "yuryapti", "sit": "o'tirdi",
               "lie": "yotdi", "fall": "yiqildi", "unknown": "noma'lum"}


def format_event(ev: dict) -> str:
    tpl = MESSAGES.get(ev["type"], "{type}")
    return tpl.format(type=ev["type"], prob=ev.get("prob") or 0.0, after_s=ev.get("after_s") or 0.0,
                      time=datetime.fromtimestamp(ev.get("t", time.time())).strftime("%H:%M:%S"))


class TelegramNotifier:
    def __init__(self, token: str | None, store: Store, chat_ids: list[str] | None = None,
                 status_text: Callable[[], str] | None = None, notify_types=("alert", "recovered", "fall_suspected")):
        self.token, self.store = token, store
        self.static_ids = [str(c) for c in (chat_ids or [])]
        self.status_text = status_text or (lambda: "Holat noma'lum")
        self.notify_types = set(notify_types)
        self._stop = threading.Event()
        self._offset = 0
        self.sent: list[tuple[str, str]] = []  # (chat_id, text), kept for the dashboard and tests

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _api(self, method: str, **params):
        r = httpx.post(f"https://api.telegram.org/bot{self.token}/{method}", json=params, timeout=35)
        r.raise_for_status()
        return r.json()

    def recipients(self) -> list[str]:
        return sorted(set(self.static_ids) | set(self.store.subscribers()))

    def send(self, text: str, chat_ids: list[str] | None = None) -> int:
        targets = chat_ids or self.recipients()
        ok = 0
        for cid in targets:
            self.sent.append((cid, text))
            if not self.enabled:
                log.info("[telegram disabled] to %s: %s", cid, text)
                continue
            try:
                self._api("sendMessage", chat_id=cid, text=text)
                ok += 1
            except Exception:
                log.exception("telegram send failed for %s", cid)
        return ok

    def notify(self, ev: dict) -> None:
        if ev["type"] in self.notify_types:
            threading.Thread(target=self.send, args=(format_event(ev),), daemon=True).start()

    # ---- bot commands (long polling) -------------------------------------------------
    def start_polling(self) -> None:
        if self.enabled:
            threading.Thread(target=self._poll, name="telegram-poll", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def handle_update(self, upd: dict) -> None:
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        cid = str(chat.get("id", ""))
        if not cid:
            return
        name = chat.get("first_name") or chat.get("title") or ""
        if text.startswith("/start"):
            self.store.add_subscriber(cid, name)
            self.send("Siz ogohlantirishlarga obuna bo'ldingiz. /status - holat, /stop - obunani bekor qilish.", [cid])
        elif text.startswith("/stop"):
            self.store.remove_subscriber(cid)
            self.send("Obuna bekor qilindi.", [cid])
        elif text.startswith("/status"):
            self.send(self.status_text(), [cid])

    def _poll(self) -> None:
        while not self._stop.is_set():
            try:
                res = self._api("getUpdates", offset=self._offset, timeout=30)
                for upd in res.get("result", []):
                    self._offset = upd["update_id"] + 1
                    self.handle_update(upd)
            except Exception:
                log.warning("telegram polling error, retrying in 5 s")
                time.sleep(5)
