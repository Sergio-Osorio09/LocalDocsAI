"""SQLite-backed session store — persists chat conversations across restarts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from localdocsai.utils.paths import ensure_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         TEXT    NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role            TEXT    NOT NULL,
    text            TEXT    NOT NULL,
    sources         TEXT    NOT NULL DEFAULT '[]',
    trace           TEXT    NOT NULL DEFAULT '{}',
    citations_valid INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages (chat_id);
"""


@dataclass
class StoredChat:
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class SessionStore:
    """Reads and writes chat sessions to a SQLite database."""

    def __init__(self, db_path: Path) -> None:
        ensure_dir(db_path.parent)
        self._db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Chat lifecycle
    # ------------------------------------------------------------------

    def create_chat(self, chat_id: str, title: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO chats (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (chat_id, title, now, now),
            )

    def rename_chat(self, chat_id: str, title: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, chat_id),
            )

    def touch_chat(self, chat_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))

    def delete_chat(self, chat_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))

    def list_chats(self) -> list[StoredChat]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) AS message_count
                FROM chats c
                LEFT JOIN messages m ON m.chat_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """
            ).fetchall()
        return [StoredChat(**dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Message persistence
    # ------------------------------------------------------------------

    def save_message(
        self,
        chat_id: str,
        role: str,
        text: str,
        sources: list[Any],
        trace: Any | None,
        citations_valid: bool,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        trace_dict = asdict(trace) if trace is not None else {}
        with self._conn() as conn:
            conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
            conn.execute(
                """
                INSERT INTO messages
                    (chat_id, role, text, sources, trace, citations_valid, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    role,
                    text,
                    json.dumps([asdict(s) for s in sources], default=str),
                    json.dumps(trace_dict, default=str),
                    int(citations_valid),
                    now,
                ),
            )

    def load_messages(self, chat_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, text, sources, trace, citations_valid "
                "FROM messages WHERE chat_id = ? ORDER BY id",
                (chat_id,),
            ).fetchall()
        return [dict(r) for r in rows]
