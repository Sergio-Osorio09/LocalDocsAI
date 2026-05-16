from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from localdocsai.indexing.embeddings import EmbeddingModel
from localdocsai.indexing.metadata_store import MetadataStore
from localdocsai.indexing.vector_store import VectorStore


@dataclass
class RetrievedChunk:
    chunk_id: int
    doc_id: str
    score: float
    text: str
    page: int
    section_path: str
    norm_code: str

    @classmethod
    def from_metadata(cls, chunk_id: int, score: float, meta: dict[str, Any]) -> RetrievedChunk:
        return cls(
            chunk_id=chunk_id,
            doc_id=meta["doc_id"],
            score=score,
            text=meta["text"],
            page=meta["page"],
            section_path=meta.get("section_path", ""),
            norm_code=meta.get("norm_code", ""),
        )


class Retriever:
    """Retrieves relevant chunks from FAISS + SQLite for a natural-language query."""

    def __init__(
        self,
        vector_store: VectorStore,
        metadata_store: MetadataStore,
        embedding_model: EmbeddingModel,
    ) -> None:
        self._vs = vector_store
        self._ms = metadata_store
        self._em = embedding_model

    def retrieve(
        self, query: str, top_k: int = 10, min_score: float = 0.3
    ) -> list[RetrievedChunk]:
        """Embed *query*, search FAISS, fetch metadata, return ranked chunks.

        Chunks with cosine similarity below *min_score* are discarded so the
        LLM never receives irrelevant context that confuses its response.
        """
        query_emb = self._em.embed([query])[0]
        hits = self._vs.search(query_emb, top_k=top_k)
        results: list[RetrievedChunk] = []
        for chunk_id, score in hits:
            if score < min_score:
                continue
            meta = self._ms.get_chunk(chunk_id)
            if meta is not None:
                results.append(RetrievedChunk.from_metadata(chunk_id, score, meta))
        return results
