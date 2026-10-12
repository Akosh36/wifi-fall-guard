"""SQLite storage for fall events and Telegram subscribers."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    t REAL NOT NULL,
    type TEXT NOT NULL,
    prob REAL,
    after_s REAL,
    note TEXT
);
CREATE TABLE IF NOT EXISTS subscribers (
    chat_id TEXT PRIMARY KEY,
    name TEXT,
    added REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path = "data/wfg.sqlite3"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def add_event(self, ev: dict) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (t, type, prob, after_s, note) VALUES (?, ?, ?, ?, ?)",
                (ev.get("t", time.time()), ev["type"], ev.get("prob"), ev.get("after_s"), ev.get("note")))
            self._conn.commit()
            return int(cur.lastrowid)

    def events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM events ORDER BY t DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def add_subscriber(self, chat_id: str, name: str = "") -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO subscribers (chat_id, name, added) VALUES (?, ?, ?)",
                               (str(chat_id), name, time.time()))
            self._conn.commit()

    def remove_subscriber(self, chat_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (str(chat_id),))
            self._conn.commit()

    def subscribers(self) -> list[str]:
        with self._lock:
            return [r["chat_id"] for r in self._conn.execute("SELECT chat_id FROM subscribers").fetchall()]
