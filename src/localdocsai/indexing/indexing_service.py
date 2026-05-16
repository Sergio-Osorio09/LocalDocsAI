"""IndexingService — parse → chunk → embed → store for a folder of documents."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from localdocsai.indexing.embeddings import EmbeddingModel
from localdocsai.indexing.metadata_store import MetadataStore, file_sha256
from localdocsai.indexing.vector_store import VectorStore

if TYPE_CHECKING:
    from localdocsai.parsers.base import ParsedDocument

_log = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".docx", ".xlsx"}


class IndexingService:
    """Indexes documents from a folder into the FAISS + SQLite stores.

    Skips files already indexed (by SHA-256 hash) so re-indexing a folder
    only processes new or modified documents.
    """

    def __init__(
        self,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        embedding_model: EmbeddingModel,
    ) -> None:
        self._ms = metadata_store
        self._vs = vector_store
        self._em = embedding_model

    def index_folder(
        self,
        folder: Path,
        progress: Callable[[str, int, int], None] | None = None,
    ) -> tuple[int, int]:
        """Index all supported documents in *folder* recursively.

        Calls *progress(filename, current, total)* as each file is processed.
        Returns *(indexed_count, skipped_count)*.
        """
        files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in _SUPPORTED]
        total = len(files)
        indexed = 0
        skipped = 0

        for i, path in enumerate(files):
            if progress:
                progress(path.name, i, total)
            try:
                sha = file_sha256(path)
                if self._ms.is_indexed(sha):
                    _log.debug("Already indexed — skipping: %s", path.name)
                    skipped += 1
                    continue

                parsed = self._parse(path)
                if parsed is None:
                    skipped += 1
                    continue

                chunks = self._chunk(parsed)
                if not chunks:
                    _log.warning("No chunks produced for %s", path.name)
                    skipped += 1
                    continue

                doc_id = self._ms.add_document(parsed, sha)
                chunk_ids = self._ms.add_chunks(doc_id, chunks)

                texts = [c.text for c in chunks]
                embeddings = self._em.embed(texts)
                emb_matrix = np.array(embeddings, dtype=np.float32)
                ids_array = np.array(chunk_ids, dtype=np.int64)
                self._vs.add(emb_matrix, ids_array)
                self._vs.save()

                _log.info("Indexed %s — %d chunks", path.name, len(chunks))
                indexed += 1

            except Exception:
                _log.error("Error indexing %s", path, exc_info=True)
                skipped += 1

        if progress:
            progress("", total, total)

        return indexed, skipped

    def _parse(self, path: Path) -> ParsedDocument | None:
        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                from localdocsai.parsers.pdf_parser import PdfParser

                return PdfParser().parse(path)
            if ext == ".docx":
                from localdocsai.parsers.docx_parser import DocxParser

                return DocxParser().parse(path)
            if ext == ".xlsx":
                from localdocsai.parsers.xlsx_parser import XlsxParser

                return XlsxParser().parse(path)
        except Exception:
            _log.error("Parse failed for %s", path, exc_info=True)
        return None

    def _chunk(self, doc: ParsedDocument) -> list:  # type: ignore[type-arg]
        from localdocsai.indexing.chunker import NormativeChunker

        return NormativeChunker().chunk(doc)
