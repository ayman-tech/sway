"""SQLite connection management and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import db_path
from app.utils.resources import resource_path

_SCHEMA_FILE = resource_path("app", "db", "schema.sql")


class Database:
    """Thin wrapper around a single SQLite connection.

    Row factory is sqlite3.Row so repositories can address columns by name.
    """

    def __init__(self, path: str | Path | None = None, check_same_thread: bool = True) -> None:
        self.path = Path(path) if path is not None else db_path()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=check_same_thread)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        # Let a writer wait briefly for a concurrent connection (GUI vs. sync thread).
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA_FILE.read_text())
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()
