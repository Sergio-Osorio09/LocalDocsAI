"""Tests for citation validator and formatter — no ML deps required."""

from __future__ import annotations

from localdocsai.core.citation import ValidationResult, format_response, validate_citations
from localdocsai.retrieval.retriever import RetrievedChunk


def _chunk(
    idx: int,
    norm_code: str = "RCD N° 001-2020",
    section_path: str = "Artículo 1°.",
    page: int = 3,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=idx,
        doc_id="test-doc",
        score=0.9,
        text="Texto de prueba.",
        page=page,
        section_path=section_path,
        norm_code=norm_code,
    )


class TestValidateCitations:
    def test_valid_single_citation(self) -> None:
        result = validate_citations("Según [1] el límite es 5 mg/m³.", 3)
        assert result.is_valid is True
        assert result.cited_indices == [1]
        assert result.invalid_indices == []

    def test_valid_multiple_citations(self) -> None:
        result = validate_citations("Ver [1] y también [3].", 3)
        assert result.is_valid is True
        assert result.cited_indices == [1, 3]

    def test_invalid_citation_too_high(self) -> None:
        result = validate_citations("Ver [5].", 3)
        assert result.is_valid is False
        assert 5 in result.invalid_indices

    def test_invalid_citation_zero(self) -> None:
        result = validate_citations("Ver [0].", 3)
        assert result.is_valid is False
        assert 0 in result.invalid_indices

    def test_no_citations(self) -> None:
        result = validate_citations("No hay citas en este texto.", 5)
        assert result.is_valid is True
        assert result.cited_indices == []

    def test_mixed_valid_and_invalid(self) -> None:
        result = validate_citations("Ver [1] y [99].", 5)
        assert result.is_valid is False
        assert 1 in result.cited_indices
        assert 99 in result.invalid_indices

    def test_repeated_citation(self) -> None:
        result = validate_citations("[1] es importante. Reitero: [1].", 3)
        assert result.is_valid is True
        assert result.cited_indices == [1, 1]

    def test_no_chunks(self) -> None:
        result = validate_citations("Sin contexto [1].", 0)
        assert result.is_valid is False

    def test_returns_validation_result(self) -> None:
        result = validate_citations("texto", 5)
        assert isinstance(result, ValidationResult)


class TestFormatResponse:
    """format_response is now a passthrough — [N] markers are kept for the
    markdown renderer to convert into cite chips in the UI."""

    def test_passthrough_preserves_citations(self) -> None:
        chunks = [_chunk(10, norm_code="RCD N° 029-2016-OS/CD")]
        text = "Ver [1] para más detalles."
        assert format_response(text, chunks) == text

    def test_passthrough_preserves_multiple_citations(self) -> None:
        chunks = [_chunk(1, page=1), _chunk(2, page=2)]
        text = "Ver [1] y [2]."
        assert format_response(text, chunks) == text

    def test_passthrough_preserves_out_of_range(self) -> None:
        chunks = [_chunk(1)]
        text = "Ver [5]."
        assert format_response(text, chunks) == text

    def test_passthrough_no_citations_unchanged(self) -> None:
        chunks = [_chunk(1)]
        text = "No hay ninguna cita aquí."
        assert format_response(text, chunks) == text
