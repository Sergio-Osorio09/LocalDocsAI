from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from localdocsai.config.settings import Settings
from localdocsai.core.citation import ValidationResult, format_response, validate_citations
from localdocsai.indexing.embeddings import EmbeddingModel
from localdocsai.indexing.metadata_store import MetadataStore
from localdocsai.indexing.vector_store import VectorStore
from localdocsai.llm.client import LLMClient
from localdocsai.llm.prompts import build_prompt
from localdocsai.retrieval.retriever import RetrievedChunk, Retriever
from localdocsai.utils.paths import get_indexes_dir, get_models_dir

_log = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    answer: str
    raw_answer: str
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    validation: ValidationResult = field(default_factory=lambda: ValidationResult(is_valid=True))


class RAGPipeline:
    """End-to-end RAG pipeline: retrieve → prompt → generate → validate → format."""

    def __init__(
        self,
        settings: Settings | None = None,
        indexes_dir: Path | None = None,
        models_dir: Path | None = None,
    ) -> None:
        s = settings or Settings.defaults()
        base = indexes_dir or get_indexes_dir()
        mdir = models_dir or get_models_dir()

        metadata_store = MetadataStore(base / "localdocsai.db")
        vector_store = VectorStore(base / "localdocsai.faiss")
        embedding_model = EmbeddingModel(mdir)

        self._retriever = Retriever(vector_store, metadata_store, embedding_model)
        self._llm = LLMClient(
            n_ctx=s.model.context_window,
            n_gpu_layers=s.model.n_gpu_layers,
        )
        self._top_k = s.retrieval.top_k
        self._max_tokens = s.model.max_tokens

        # One-shot cleanup: drop any chunk rows in SQLite whose embedding
        # never made it into FAISS (e.g. from an earlier indexing run that
        # crashed mid-batch). Leaving them would let retrieve() return
        # 'phantom' rows whose vector is implicitly zero.
        _cleanup_orphan_chunks(metadata_store, vector_store)

    def ask(self, question: str) -> RAGResponse:
        """Answer *question* using the indexed documents."""
        chunks = self._retriever.retrieve(question, top_k=self._top_k)

        if not chunks:
            no_ctx = "No se encontraron documentos relevantes para esta consulta."
            return RAGResponse(
                answer=no_ctx,
                raw_answer=no_ctx,
                retrieved_chunks=[],
                validation=ValidationResult(is_valid=True),
            )

        system_prompt, user_message = build_prompt(question, chunks)
        raw = self._llm.generate(system_prompt, user_message, max_tokens=self._max_tokens)
        validation = validate_citations(raw, len(chunks))
        answer = format_response(raw, chunks)

        return RAGResponse(
            answer=answer,
            raw_answer=raw,
            retrieved_chunks=chunks,
            validation=validation,
        )


def _cleanup_orphan_chunks(metadata_store: MetadataStore, vector_store: VectorStore) -> int:
    """Remove SQLite chunk rows whose primary key is not present in FAISS.

    Returns the number of chunks deleted (0 if everything is consistent).
    Safe to call on every pipeline construction — exits in O(n) time over
    the chunk count when there are no orphans.
    """
    try:
        faiss_ids = set(vector_store.all_ids())
    except Exception:
        _log.warning("Could not enumerate FAISS ids — skipping orphan cleanup", exc_info=True)
        return 0

    if not faiss_ids:
        # An empty index is not necessarily corrupt (fresh install); only
        # warn if SQLite has data that FAISS can't back.
        if metadata_store.get_chunk_count() == 0:
            return 0

    db_ids = metadata_store.all_chunk_ids()
    orphans = [cid for cid in db_ids if cid not in faiss_ids]
    if not orphans:
        return 0

    _log.warning("Cleaning %d orphan chunks (in DB but missing FAISS vectors)", len(orphans))
    metadata_store.delete_chunks_by_id(orphans)
    return len(orphans)
