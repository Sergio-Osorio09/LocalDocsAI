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

    def delete_document(self, doc_pk: int) -> None:
        """Delete a document row by its integer primary key.

        Chunk rows referencing the document cascade-delete via the
        ON DELETE CASCADE FK in the schema, so this leaves no orphans
        on the SQL side.
        """
        with self._conn() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_pk,))

    def delete_chunks_by_id(self, chunk_ids: list[int]) -> None:
        """Bulk-delete chunks by their integer PKs. No-op for an empty list.

        Used to clean up orphan rows whose embeddings never made it into
        the FAISS index (e.g. when add_document/add_chunks succeeded but
        the embedding step failed in a prior indexing run).
        """
        if not chunk_ids:
            return
        with self._conn() as conn:
            # SQLite caps the parameter count per statement, so batch.
            for i in range(0, len(chunk_ids), 900):
                batch = chunk_ids[i : i + 900]
                placeholders = ",".join(["?"] * len(batch))
                conn.execute(
                    f"DELETE FROM chunks WHERE id IN ({placeholders})",  # noqa: S608
                    batch,
                )

    def all_chunk_ids(self) -> list[int]:
        """Return every chunk primary key in the store."""
        with self._conn() as conn:
            return [r[0] for r in conn.execute("SELECT id FROM chunks").fetchall()]

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
                    doc.source_path.resolve().as_posix(),
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

    def get_indexed_paths_in_folder(self, folder: Path) -> set[str]:
        """Return absolute posix-path strings of all indexed documents under *folder*."""
        prefixes = [folder.resolve().as_posix() + "/"]
        try:
            rel = folder.resolve().relative_to(Path.cwd())
            prefixes.append(rel.as_posix() + "/")
        except ValueError:
            pass
        conditions = " OR ".join(["path LIKE ?"] * len(prefixes))
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT path FROM documents WHERE {conditions}",  # noqa: S608
                [p + "%" for p in prefixes],
            ).fetchall()
        result: set[str] = set()
        for (p,) in rows:
            result.add(p)
            result.add(Path(p).resolve().as_posix())
        return result

    def count_docs_in_folder(self, folder: Path) -> int:
        """Return how many indexed documents live under *folder*.

        Handles both absolute paths (new records) and relative paths (legacy
        records indexed via CLI from the project root).
        """
        prefixes = [folder.resolve().as_posix() + "/"]
        try:
            rel = folder.resolve().relative_to(Path.cwd())
            prefixes.append(rel.as_posix() + "/")
        except ValueError:
            pass
        conditions = " OR ".join(["path LIKE ?"] * len(prefixes))
        with self._conn() as conn:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM documents WHERE {conditions}",  # noqa: S608
                    [p + "%" for p in prefixes],
                ).fetchone()[0]
            )
