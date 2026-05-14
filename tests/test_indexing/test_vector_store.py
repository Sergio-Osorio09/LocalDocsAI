"""Tests for VectorStore (FAISS) — requires faiss-cpu."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed")

from localdocsai.indexing.embeddings import DIMENSION  # noqa: E402
from localdocsai.indexing.vector_store import VectorStore  # noqa: E402


def _random_embeddings(n: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vecs = rng.standard_normal((n, DIMENSION)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms  # L2-normalize (cosine sim via IndexFlatIP)


class TestVectorStore:
    def test_starts_empty(self, tmp_path: Path) -> None:
        store = VectorStore(tmp_path / "test.faiss")
        assert store.total_vectors == 0

    def test_add_increases_count(self, tmp_path: Path) -> None:
        store = VectorStore(tmp_path / "test.faiss")
        embeddings = _random_embeddings(5)
        ids = np.array([1, 2, 3, 4, 5], dtype=np.int64)
        store.add(embeddings, ids)
        assert store.total_vectors == 5

    def test_search_returns_results(self, tmp_path: Path) -> None:
        store = VectorStore(tmp_path / "test.faiss")
        embeddings = _random_embeddings(10)
        ids = np.arange(1, 11, dtype=np.int64)
        store.add(embeddings, ids)
        results = store.search(embeddings[0], top_k=3)
        assert len(results) == 3

    def test_search_result_format(self, tmp_path: Path) -> None:
        store = VectorStore(tmp_path / "test.faiss")
        embeddings = _random_embeddings(5)
        ids = np.array([10, 20, 30, 40, 50], dtype=np.int64)
        store.add(embeddings, ids)
        results = store.search(embeddings[0], top_k=2)
        chunk_id, score = results[0]
        assert isinstance(chunk_id, int)
        assert isinstance(score, float)

    def test_exact_match_is_first(self, tmp_path: Path) -> None:
        store = VectorStore(tmp_path / "test.faiss")
        embeddings = _random_embeddings(5)
        ids = np.array([10, 20, 30, 40, 50], dtype=np.int64)
        store.add(embeddings, ids)
        # Query with the exact vector of id=20 (index 1)
        results = store.search(embeddings[1], top_k=1)
        assert results[0][0] == 20
        assert results[0][1] == pytest.approx(1.0, abs=1e-5)

    def test_scores_descending(self, tmp_path: Path) -> None:
        store = VectorStore(tmp_path / "test.faiss")
        embeddings = _random_embeddings(10)
        ids = np.arange(1, 11, dtype=np.int64)
        store.add(embeddings, ids)
        results = store.search(embeddings[0], top_k=5)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_save_and_reload(self, tmp_path: Path) -> None:
        index_path = tmp_path / "test.faiss"
        store = VectorStore(index_path)
        embeddings = _random_embeddings(5)
        ids = np.arange(1, 6, dtype=np.int64)
        store.add(embeddings, ids)
        store.save()

        store2 = VectorStore(index_path)
        assert store2.total_vectors == 5
        results = store2.search(embeddings[0], top_k=1)
        assert results[0][0] == 1

    def test_top_k_capped_by_total(self, tmp_path: Path) -> None:
        store = VectorStore(tmp_path / "test.faiss")
        embeddings = _random_embeddings(3)
        ids = np.array([1, 2, 3], dtype=np.int64)
        store.add(embeddings, ids)
        results = store.search(embeddings[0], top_k=10)
        assert len(results) == 3  # only 3 vectors exist
