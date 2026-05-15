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
    def test_replaces_citation_with_norm_code(self) -> None:
        chunks = [_chunk(10, norm_code="RCD N° 029-2016-OS/CD")]
        out = format_response("Ver [1] para más detalles.", chunks)
        assert "RCD N° 029-2016-OS/CD" in out
        assert "[1]" not in out

    def test_replaces_citation_with_page(self) -> None:
        chunks = [_chunk(10, page=17)]
        out = format_response("Ver [1].", chunks)
        assert "p.17" in out

    def test_replaces_citation_with_section_last_segment(self) -> None:
        chunks = [_chunk(10, section_path="1. OBJETO > Artículo 5°.")]
        out = format_response("Ver [1].", chunks)
        assert "Artículo 5°." in out
        assert "1. OBJETO" not in out

    def test_multiple_citations_replaced(self) -> None:
        chunks = [_chunk(1, page=1), _chunk(2, page=2)]
        out = format_response("Ver [1] y [2].", chunks)
        assert "p.1" in out
        assert "p.2" in out

    def test_out_of_range_citation_unchanged(self) -> None:
        chunks = [_chunk(1)]
        out = format_response("Ver [5].", chunks)
        assert "[5]" in out

    def test_no_citations_unchanged(self) -> None:
        chunks = [_chunk(1)]
        text = "No hay ninguna cita aquí."
        assert format_response(text, chunks) == text

    def test_empty_norm_code_omitted(self) -> None:
        chunks = [_chunk(1, norm_code="", section_path="Art. 1°.", page=2)]
        out = format_response("Ver [1].", chunks)
        assert "Art. 1°." in out
        assert out.startswith("Ver (")

    def test_empty_section_path_omitted(self) -> None:
        chunks = [_chunk(1, norm_code="RCD N° 001", section_path="", page=5)]
        out = format_response("Ver [1].", chunks)
        assert "RCD N° 001" in out
        assert "p.5" in out
