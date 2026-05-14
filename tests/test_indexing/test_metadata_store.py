"""Tests for MetadataStore (SQLite) — no ML deps required."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from localdocsai.indexing.chunker import Chunk
from localdocsai.indexing.metadata_store import MetadataStore, file_sha256
from localdocsai.parsers.base import PageContent, ParsedDocument


def _make_doc(tmp_path: Path, name: str = "test.pdf") -> ParsedDocument:
    return ParsedDocument(
        source_path=tmp_path / name,
        doc_type="pdf",
        title=name,
        pages=[PageContent(1, "Artículo 1°. Contenido de prueba.")],
        norm_codes=["RCD N° 029-2016-OS/CD"],
    )


def _make_chunks(doc_id: str = "test", n: int = 3) -> list[Chunk]:
    return [
        Chunk(
            doc_id=doc_id,
            chunk_index=i,
            page=1,
            section_path=f"Artículo {i + 1}°.",
            norm_code="RCD N° 029-2016-OS/CD",
            text=f"Texto del chunk {i}.",
            token_count=10,
        )
        for i in range(n)
    ]


class TestFileSha256:
    def test_returns_hex_string(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_bytes(b"hello")
        digest = file_sha256(f)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_same_content_same_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"content")
        f2.write_bytes(b"content")
        assert file_sha256(f1) == file_sha256(f2)

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"aaa")
        f2.write_bytes(b"bbb")
        assert file_sha256(f1) != file_sha256(f2)


class TestMetadataStoreSchema:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        MetadataStore(db)
        assert db.exists()

    def test_empty_on_creation(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        assert store.get_document_count() == 0
        assert store.get_chunk_count() == 0


class TestMetadataStoreDocuments:
    def test_add_document_returns_int(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        doc_id = store.add_document(doc, "abc123")
        assert isinstance(doc_id, int)
        assert doc_id > 0

    def test_document_count_increments(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        store.add_document(doc, "hash1")
        assert store.get_document_count() == 1

    def test_is_indexed_true_after_add(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        store.add_document(doc, "myhash")
        assert store.is_indexed("myhash") is True

    def test_is_indexed_false_for_unknown(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        assert store.is_indexed("unknown") is False

    def test_duplicate_hash_raises(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        store.add_document(doc, "samehash")
        with pytest.raises(sqlite3.IntegrityError):
            store.add_document(doc, "samehash")


class TestMetadataStoreChunks:
    def test_add_chunks_returns_ids(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        doc_db_id = store.add_document(doc, "h1")
        ids = store.add_chunks(doc_db_id, _make_chunks(n=3))
        assert len(ids) == 3
        assert all(isinstance(i, int) and i > 0 for i in ids)

    def test_chunk_ids_are_sequential(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        doc_db_id = store.add_document(doc, "h1")
        ids = store.add_chunks(doc_db_id, _make_chunks(n=3))
        assert ids == sorted(ids)

    def test_get_chunk_by_id(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        doc_db_id = store.add_document(doc, "h1")
        ids = store.add_chunks(doc_db_id, _make_chunks(n=2))
        chunk = store.get_chunk(ids[0])
        assert chunk is not None
        assert chunk["chunk_index"] == 0
        assert chunk["norm_code"] == "RCD N° 029-2016-OS/CD"

    def test_get_chunk_nonexistent_returns_none(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        assert store.get_chunk(9999) is None

    def test_chunk_count(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        doc_db_id = store.add_document(doc, "h1")
        store.add_chunks(doc_db_id, _make_chunks(n=5))
        assert store.get_chunk_count() == 5

    def test_section_path_stored(self, tmp_path: Path) -> None:
        store = MetadataStore(tmp_path / "test.db")
        doc = _make_doc(tmp_path)
        doc_db_id = store.add_document(doc, "h1")
        ids = store.add_chunks(doc_db_id, _make_chunks(n=1))
        chunk = store.get_chunk(ids[0])
        assert chunk is not None
        assert "Artículo" in chunk["section_path"]
