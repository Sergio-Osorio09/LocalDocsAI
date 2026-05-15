"""Tests for Retriever — requires faiss-cpu."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed")

from localdocsai.indexing.embeddings import DIMENSION  # noqa: E402
from localdocsai.indexing.metadata_store import MetadataStore  # noqa: E402
from localdocsai.indexing.vector_store import VectorStore  # noqa: E402
from localdocsai.retrieval.retriever import RetrievedChunk, Retriever  # noqa: E402


def _normalized(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vecs = rng.standard_normal((n, DIMENSION)).astype(np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def _make_retriever(tmp_path: Path, n: int = 5) -> tuple[Retriever, list[int]]:
    """Create a Retriever backed by real FAISS + SQLite stores with *n* chunks."""
    from localdocsai.indexing.chunker import Chunk
    from localdocsai.parsers.base import PageContent, ParsedDocument

    db_path = tmp_path / "test.db"
    faiss_path = tmp_path / "test.faiss"

    ms = MetadataStore(db_path)
    vs = VectorStore(faiss_path)

    doc = ParsedDocument(
        source_path=tmp_path / "test.pdf",
        doc_type="pdf",
        title="Test",
        pages=[PageContent(1, "Test content.")],
        norm_codes=["RCD N° 001-2020"],
    )
    doc_id = ms.add_document(doc, "testhash")
    chunks = [
        Chunk(
            doc_id="test",
            chunk_index=i,
            page=i + 1,
            section_path=f"Artículo {i + 1}°.",
            norm_code="RCD N° 001-2020",
            text=f"Texto del artículo {i + 1}.",
            token_count=10,
        )
        for i in range(n)
    ]
    chunk_ids = ms.add_chunks(doc_id, chunks)
    embeddings = _normalized(n)
    vs.add(embeddings, np.array(chunk_ids, dtype=np.int64))

    mock_em = MagicMock()
    mock_em.embed.return_value = embeddings  # query returns same matrix for determinism

    retriever = Retriever(vs, ms, mock_em)
    return retriever, chunk_ids


class TestRetrievedChunk:
    def test_from_metadata(self) -> None:
        meta = {
            "doc_id": "doc1",
            "text": "hello",
            "page": 3,
            "section_path": "Artículo 1°.",
            "norm_code": "RCD N° 001",
        }
        chunk = RetrievedChunk.from_metadata(42, 0.95, meta)
        assert chunk.chunk_id == 42
        assert chunk.score == 0.95
        assert chunk.doc_id == "doc1"
        assert chunk.page == 3

    def test_from_metadata_missing_optional_fields(self) -> None:
        meta = {"doc_id": "d", "text": "t", "page": 1}
        chunk = RetrievedChunk.from_metadata(1, 0.5, meta)
        assert chunk.section_path == ""
        assert chunk.norm_code == ""


class TestRetriever:
    def test_retrieve_returns_list(self, tmp_path: Path) -> None:
        retriever, _ = _make_retriever(tmp_path, n=5)
        results = retriever.retrieve("consulta de prueba", top_k=3)
        assert isinstance(results, list)
        assert len(results) == 3

    def test_retrieve_result_type(self, tmp_path: Path) -> None:
        retriever, _ = _make_retriever(tmp_path, n=5)
        results = retriever.retrieve("consulta", top_k=1)
        assert len(results) == 1
        chunk = results[0]
        assert isinstance(chunk, RetrievedChunk)
        assert isinstance(chunk.chunk_id, int)
        assert isinstance(chunk.score, float)
        assert isinstance(chunk.text, str)

    def test_retrieve_scores_descending(self, tmp_path: Path) -> None:
        retriever, _ = _make_retriever(tmp_path, n=10)
        results = retriever.retrieve("consulta", top_k=5)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_retrieve_top_k_capped(self, tmp_path: Path) -> None:
        retriever, _ = _make_retriever(tmp_path, n=3)
        results = retriever.retrieve("consulta", top_k=10)
        assert len(results) == 3

    def test_retrieve_metadata_populated(self, tmp_path: Path) -> None:
        retriever, _ = _make_retriever(tmp_path, n=3)
        results = retriever.retrieve("consulta", top_k=1)
        chunk = results[0]
        assert chunk.norm_code == "RCD N° 001-2020"
        assert "Artículo" in chunk.section_path

    def test_retrieve_empty_index(self, tmp_path: Path) -> None:
        from localdocsai.indexing.metadata_store import MetadataStore
        from localdocsai.indexing.vector_store import VectorStore

        ms = MetadataStore(tmp_path / "empty.db")
        vs = VectorStore(tmp_path / "empty.faiss")
        mock_em = MagicMock()
        mock_em.embed.return_value = _normalized(1)
        retriever = Retriever(vs, ms, mock_em)
        results = retriever.retrieve("consulta", top_k=5)
        assert results == []
