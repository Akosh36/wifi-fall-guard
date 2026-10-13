"""SQLite storage: events, Telegram subscribers, settings and the status history."""

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
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS history (
    t REAL PRIMARY KEY,
    state TEXT,
    activity TEXT,
    fall REAL,
    motion REAL,
    x REAL,
    y REAL,
    breath REAL,
    heart REAL,
    security TEXT
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

    def events(self, limit: int = 50, since: float | None = None) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM events WHERE t > ? ORDER BY t DESC, id DESC LIMIT ?",
                                      (since or 0.0, limit)).fetchall()
        return [dict(r) for r in rows]

    HISTORY_COLS = ("t", "state", "activity", "fall", "motion", "x", "y", "breath", "heart", "security")

    def add_history(self, row: dict) -> None:
        with self._lock:
            self._conn.execute(f"INSERT OR REPLACE INTO history VALUES ({','.join('?' * len(self.HISTORY_COLS))})",
                               tuple(row.get(c) for c in self.HISTORY_COLS))
            self._conn.commit()

    def history(self, since: float = 0.0, until: float | None = None, limit: int = 5000) -> list[dict]:
        """Oldest first, so a client can page forward with ``since`` = last ``t`` it has."""
        with self._lock:
            rows = self._conn.execute("SELECT * FROM history WHERE t > ? AND t <= ? ORDER BY t LIMIT ?",
                                      (since, until if until is not None else 1e12, limit)).fetchall()
        return [dict(r) for r in rows]

    def prune_history(self, older_than: float) -> int:
        with self._lock:
            n = self._conn.execute("DELETE FROM history WHERE t < ?", (older_than,)).rowcount
            self._conn.commit()
        return n

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            self._conn.commit()

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
