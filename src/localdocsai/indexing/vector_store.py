from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from localdocsai.indexing.embeddings import DIMENSION
from localdocsai.utils.paths import ensure_dir


class VectorStore:
    """FAISS vector store with IndexFlatIP (cosine similarity via L2-normalized vectors).

    Uses IndexIDMap so SQLite chunk IDs can be used directly as FAISS IDs,
    making lookup trivial: FAISS returns chunk_id → query SQLite.
    """

    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path
        self._index = None  # lazy-loaded on first access

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_empty_index(self) -> Any:
        import faiss

        base = faiss.IndexFlatIP(DIMENSION)
        return faiss.IndexIDMap(base)

    @property
    def _faiss_index(self) -> Any:
        if self._index is None:
            import faiss

            if self._index_path.exists():
                self._index = faiss.read_index(str(self._index_path))
            else:
                self._index = self._build_empty_index()
        return self._index

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, embeddings: np.ndarray, chunk_ids: np.ndarray) -> None:
        """Add *embeddings* indexed by *chunk_ids* (SQLite PKs, int64)."""
        vecs = np.ascontiguousarray(embeddings, dtype=np.float32)
        ids = np.ascontiguousarray(chunk_ids, dtype=np.int64)
        self._faiss_index.add_with_ids(vecs, ids)

    def save(self) -> None:
        """Persist the index to disk."""
        import faiss

        ensure_dir(self._index_path.parent)
        faiss.write_index(self._faiss_index, str(self._index_path))

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> list[tuple[int, float]]:
        """Return (chunk_id, score) pairs ordered by descending similarity."""
        query = np.ascontiguousarray(query_embedding.reshape(1, -1), dtype=np.float32)
        scores, ids = self._faiss_index.search(query, top_k)
        return [
            (int(chunk_id), float(score))
            for chunk_id, score in zip(ids[0], scores[0], strict=True)
            if chunk_id >= 0  # FAISS returns -1 for unfilled slots
        ]

    @property
    def total_vectors(self) -> int:
        return int(self._faiss_index.ntotal)
