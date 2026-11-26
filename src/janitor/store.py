"""SQLite storage: a small key/value table for settings and state, and the run history."""
import asyncio
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

HISTORY_LIMIT = 50


class Store:
    """One connection per operation, run in a worker thread, so the event loop never waits on disk."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get_sync(self, key: str, default: Any = None) -> Any:
        with closing(self._connect()) as db:
            row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def set_sync(self, key: str, value: Any) -> None:
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value)))

    def delete_sync(self, key: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM kv WHERE key=?", (key,))

    def _add_history(self, entry: dict) -> None:
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO history(data) VALUES(?)", (json.dumps(entry),))
            db.execute("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT ?)",
                       (HISTORY_LIMIT,))

    def _history(self) -> list[dict]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT data FROM history ORDER BY id DESC").fetchall()
        return [json.loads(r[0]) for r in rows]

    async def get(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self.get_sync, key, default)

    async def set(self, key: str, value: Any) -> None:
        await asyncio.to_thread(self.set_sync, key, value)

    async def add_history(self, entry: dict) -> None:
        await asyncio.to_thread(self._add_history, entry)

    async def history(self) -> list[dict]:
        return await asyncio.to_thread(self._history)
