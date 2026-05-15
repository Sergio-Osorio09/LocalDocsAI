from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

DIMENSION = 1024
MODEL_NAME = "BAAI/bge-m3"


class EmbeddingModel:
    """Lazy-loaded BGE-M3 embedding model via sentence-transformers.

    The model is only loaded on first call to embed(), so startup is fast
    when the embedding model is not needed (e.g., running `parse` or `chunk`).
    """

    def __init__(self, model_dir: Path | None = None) -> None:
        self._model_dir = model_dir
        self._model: SentenceTransformer | None = None

    def _load(self) -> SentenceTransformer:
        from sentence_transformers import SentenceTransformer

        cache_folder = str(self._model_dir) if self._model_dir else None
        model: Any = SentenceTransformer(MODEL_NAME, cache_folder=cache_folder)
        return cast(SentenceTransformer, model)

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = self._load()
        return self._model

    def embed(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Return L2-normalized embeddings of shape (N, DIMENSION).

        Vectors are normalized so that IndexFlatIP acts as cosine similarity.
        """
        raw = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 50,
        )
        return np.array(raw, dtype=np.float32)
