"""Alerts for relatives through a Telegram bot.

Create a bot with @BotFather, put the token in ``WFG_TELEGRAM_TOKEN``. Each
relative opens the bot and sends ``/start``; from then on they receive alerts.
``/status`` replies with the current state, ``/arm`` and ``/disarm`` switch the
home security mode, ``/stop`` unsubscribes. When the server asks "call an
ambulance?" after a fall, the message has two buttons; ``/call`` and
``/cancel`` do the same.
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
    "intrusion": "🚨 QO'RIQLASH: {time} da uyda harakat aniqlandi! Uyda hech kim bo'lmasligi kerak edi.",
    "intrusion_ended": "ℹ️ {time}: harakat to'xtadi, xona yana bo'sh. Qo'riqlash davom etmoqda.",
    "armed": "🛡 Qo'riqlash rejimi yoqildi ({time}). 30 soniyadan keyin kuzatuv boshlanadi.",
    "disarmed": "🏠 Qo'riqlash rejimi o'chirildi ({time}).",
    "ask_owner": "❓ {time}: odam yiqilib, {down_min:g} daqiqadan beri turmayapti. Holati: {reason}.\n"
                 "Tez yordam ({number}) chaqirilsinmi?",
    "emergency": "🚑 XAVFLI HOLAT ({time}): odam {down_min:g} daqiqadan beri turmayapti, {reason}.\n"
                 "{cancel_s:.0f} soniya ichida hech kim bekor qilmasa, tez yordam ({number}) chaqiriladi.",
    "emergency_call": "🚑 TEZ YORDAM CHAQIRILDI ({number}), {time}. Qaror: {by}.\nSabab: {reason}.{address_line}",
    "emergency_cancelled": "✋ Tez yordam chaqirilmadi: {by}. Kuzatuv davom etmoqda.",
    "resolved": "✅ Odam turdi ({time}). Tez yordam kerak emas.",
    "police_ask": "🚨 QO'RIQLASH ({time}): uyda begona harakat aniqlandi.\nPolitsiya ({number}) chaqirilsinmi? "
                  "Uyga o'zingiz yoki tanishingiz kirgan bo'lsa, \"Kerak emas\"ni bosing.",
    "police_countdown": "🚨 XAVFLI ({time}): {reason}.\n{cancel_s:.0f} soniya ichida hech kim bekor qilmasa, "
                        "politsiya ({number}) chaqiriladi.",
    "police_call": "🚓 POLITSIYA CHAQIRILDI ({number}), {time}. Qaror: {by}.\nSabab: {reason}.{address_line}",
    "police_cancelled": "✋ Politsiya chaqirilmadi: {by}.",
}

# inline buttons under the "call?" messages; the callback data comes back in handle_update
CALL_BUTTONS = {
    "ask_owner": [[{"text": "🚑 Ha, chaqiring", "callback_data": "esc:yes"},
                   {"text": "❌ Kerak emas", "callback_data": "esc:no"}]],
    "emergency": [[{"text": "🚑 Hozir chaqirish", "callback_data": "esc:yes"},
                   {"text": "✋ Bekor qilish", "callback_data": "esc:no"}]],
    "police_ask": [[{"text": "🚓 Ha, chaqiring", "callback_data": "pol:yes"},
                    {"text": "❌ Kerak emas", "callback_data": "pol:no"}]],
    "police_countdown": [[{"text": "🚓 Hozir chaqirish", "callback_data": "pol:yes"},
                          {"text": "✋ Bekor qilish", "callback_data": "pol:no"}]],
}

ACTIVITY_UZ = {"empty": "xona bo'sh", "still": "qimirlamayapti", "walk": "yuryapti", "sit": "o'tirdi",
               "lie": "yotdi", "fall": "yiqildi", "unknown": "noma'lum"}


def format_event(ev: dict) -> str:
    tpl = MESSAGES.get(ev["type"], "{type}")
    fields = {"reason": "", "number": "103", "down_min": 0.0, "cancel_s": 30.0, "by": "", **ev}
    fields.update(prob=ev.get("prob") or 0.0, after_s=ev.get("after_s") or 0.0,
                  address_line=f"\nManzil: {ev['address']}" if ev.get("address") else "",
                  time=datetime.fromtimestamp(ev.get("t", time.time())).strftime("%H:%M:%S"))
    return tpl.format(**fields)


class TelegramNotifier:
    def __init__(self, token: str | None, store: Store, chat_ids: list[str] | None = None,
                 status_text: Callable[[], str] | None = None,
                 notify_types=("alert", "recovered", "fall_suspected", "intrusion", "intrusion_ended", "armed",
                               "disarmed", "ask_owner", "emergency", "emergency_call", "emergency_cancelled",
                               "police_ask", "police_countdown", "police_call", "police_cancelled"),
                 # "resolved" is not sent: the detector's "recovered" message already says the person got up
                 on_command: Callable[[str, str], str | None] | None = None):
        self.token, self.store = token, store
        self.static_ids = [str(c) for c in (chat_ids or [])]
        self.status_text = status_text or (lambda: "Holat noma'lum")
        self.notify_types = set(notify_types)
        self.on_command = on_command or (lambda name, who: None)
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

    def send(self, text: str, chat_ids: list[str] | None = None, buttons: list | None = None) -> int:
        targets = chat_ids or self.recipients()
        ok = 0
        for cid in targets:
            self.sent.append((cid, text))
            if not self.enabled:
                log.info("[telegram disabled] to %s: %s", cid, text)
                continue
            try:
                extra = {"reply_markup": {"inline_keyboard": buttons}} if buttons else {}
                self._api("sendMessage", chat_id=cid, text=text, **extra)
                ok += 1
            except Exception:
                log.exception("telegram send failed for %s", cid)
        return ok

    def notify(self, ev: dict) -> None:
        if ev["type"] in self.notify_types:
            threading.Thread(target=self.send, args=(format_event(ev), None, CALL_BUTTONS.get(ev["type"])),
                             daemon=True).start()

    def send_photo(self, jpeg: bytes, caption: str) -> int:
        """Camera snapshot (optional add-on) to every recipient."""
        ok = 0
        for cid in self.recipients():
            self.sent.append((cid, f"[photo] {caption}"))
            if not self.enabled:
                continue
            try:
                httpx.post(f"https://api.telegram.org/bot{self.token}/sendPhoto", data={"chat_id": cid, "caption": caption},
                           files={"photo": ("snapshot.jpg", jpeg, "image/jpeg")}, timeout=35).raise_for_status()
                ok += 1
            except Exception:
                log.exception("telegram photo failed for %s", cid)
        return ok

    def _allowed(self, cid: str) -> bool:
        # chat_ids from the config are the owners; without them any subscriber may give commands
        return cid in (self.static_ids or self.recipients())

    # ---- bot commands (long polling) -------------------------------------------------
    def start_polling(self) -> None:
        if self.enabled:
            threading.Thread(target=self._poll, name="telegram-poll", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def handle_update(self, upd: dict) -> None:
        if upd.get("callback_query"):
            return self._handle_button(upd["callback_query"])
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        cid = str(chat.get("id", ""))
        if not cid:
            return
        name = chat.get("first_name") or chat.get("title") or ""
        if text.startswith("/start"):
            self.store.add_subscriber(cid, name)
            self.send("Siz ogohlantirishlarga obuna bo'ldingiz.\n/status - holat\n/arm - qo'riqlashni yoqish\n"
                      "/disarm - qo'riqlashni o'chirish\n/call - tez yordam chaqirishga roziman\n"
                      "/cancel - tez yordam kerak emas\n/stop - obunani bekor qilish", [cid])
        elif text.startswith("/stop"):
            self.store.remove_subscriber(cid)
            self.send("Obuna bekor qilindi.", [cid])
        elif text.startswith("/status"):
            self.send(self.status_text(), [cid])
        elif text.startswith(("/arm", "/disarm", "/call", "/cancel")):
            if not self._allowed(cid):
                self.send("Sizda bu buyruq uchun ruxsat yo'q.", [cid])
                return
            reply = self.on_command(text.split()[0].lstrip("/").split("@")[0], f"Telegram: {name or cid}")
            if reply:
                self.send(reply, [cid])

    def _handle_button(self, q: dict) -> None:
        cid = str((q.get("message") or {}).get("chat", {}).get("id") or (q.get("from") or {}).get("id", ""))
        name = (q.get("from") or {}).get("first_name") or cid
        allowed = self._allowed(cid)
        reply = None
        commands = {"esc:yes": "call", "esc:no": "cancel", "pol:yes": "police", "pol:no": "nopolice"}
        if allowed and q.get("data") in commands:
            reply = self.on_command(commands[q["data"]], f"Telegram: {name}")
        if self.enabled:
            try:
                self._api("answerCallbackQuery", callback_query_id=q.get("id"),
                          text=reply or ("Qabul qilindi" if allowed else "Ruxsat yo'q"))
            except Exception:
                log.warning("answerCallbackQuery failed")

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
