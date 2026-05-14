from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from localdocsai.indexing.chunker import Chunk
from localdocsai.parsers.base import ParsedDocument
from localdocsai.utils.paths import derive_doc_id, ensure_dir

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      TEXT    NOT NULL,
    path        TEXT    NOT NULL,
    hash_sha256 TEXT    NOT NULL UNIQUE,
    doc_type    TEXT    NOT NULL,
    indexed_at  TEXT    NOT NULL,
    page_count  INTEGER NOT NULL DEFAULT 0,
    norm_codes  TEXT    NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    doc_id       TEXT    NOT NULL,
    chunk_index  INTEGER NOT NULL,
    page         INTEGER NOT NULL,
    section_path TEXT    NOT NULL DEFAULT '',
    norm_code    TEXT    NOT NULL DEFAULT '',
    text         TEXT    NOT NULL,
    token_count  INTEGER NOT NULL,
    group_tags   TEXT    NOT NULL DEFAULT '',
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id  ON chunks    (doc_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents (hash_sha256);
"""


# ---------------------------------------------------------------------------
# File hashing
# ---------------------------------------------------------------------------


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of *path* (streaming, safe for large files)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class MetadataStore:
    """SQLite-backed store for document and chunk metadata."""

    def __init__(self, db_path: Path) -> None:
        ensure_dir(db_path.parent)
        self._db_path = db_path
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

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
    # Write operations
    # ------------------------------------------------------------------

    def add_document(self, doc: ParsedDocument, hash_sha256: str) -> int:
        """Insert a document record and return its integer primary key."""
        now = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents
                    (doc_id, path, hash_sha256, doc_type, indexed_at, page_count, norm_codes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    derive_doc_id(doc.source_path),
                    str(doc.source_path),
                    hash_sha256,
                    doc.doc_type,
                    now,
                    doc.page_count,
                    json.dumps(doc.norm_codes),
                ),
            )
            row_id: int = cursor.lastrowid  # type: ignore[assignment]
            return row_id

    def add_chunks(self, document_id: int, chunks: list[Chunk]) -> list[int]:
        """Insert chunks for *document_id* and return their integer primary keys."""
        ids: list[int] = []
        with self._conn() as conn:
            for chunk in chunks:
                cursor = conn.execute(
                    """
                    INSERT INTO chunks
                        (document_id, doc_id, chunk_index, page,
                         section_path, norm_code, text, token_count, group_tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        chunk.doc_id,
                        chunk.chunk_index,
                        chunk.page,
                        chunk.section_path,
                        chunk.norm_code,
                        chunk.text,
                        chunk.token_count,
                        chunk.group_tags,
                    ),
                )
                ids.append(cursor.lastrowid)  # type: ignore[arg-type]
        return ids

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def is_indexed(self, hash_sha256: str) -> bool:
        """Return True if a document with this hash is already in the store."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM documents WHERE hash_sha256 = ?", (hash_sha256,)
            ).fetchone()
            return row is not None

    def get_chunk(self, chunk_id: int) -> dict[str, Any] | None:
        """Return chunk metadata by its SQLite primary key, or None."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
            return dict(row) if row else None

    def get_document_count(self) -> int:
        with self._conn() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def get_chunk_count(self) -> int:
        with self._conn() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
