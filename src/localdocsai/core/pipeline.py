from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from localdocsai.core.citation import ValidationResult, format_response, validate_citations
from localdocsai.indexing.embeddings import EmbeddingModel
from localdocsai.indexing.metadata_store import MetadataStore
from localdocsai.indexing.vector_store import VectorStore
from localdocsai.llm.client import LLMClient
from localdocsai.llm.prompts import build_prompt
from localdocsai.retrieval.retriever import RetrievedChunk, Retriever
from localdocsai.utils.paths import get_indexes_dir, get_models_dir


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
        indexes_dir: Path | None = None,
        models_dir: Path | None = None,
        top_k: int = 5,
        max_tokens: int = 1024,
        n_gpu_layers: int = 0,
    ) -> None:
        base = indexes_dir or get_indexes_dir()
        mdir = models_dir or get_models_dir()

        metadata_store = MetadataStore(base / "localdocsai.db")
        vector_store = VectorStore(base / "localdocsai.faiss")
        embedding_model = EmbeddingModel(mdir)

        self._retriever = Retriever(vector_store, metadata_store, embedding_model)
        self._llm = LLMClient(n_gpu_layers=n_gpu_layers)
        self._top_k = top_k
        self._max_tokens = max_tokens

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
