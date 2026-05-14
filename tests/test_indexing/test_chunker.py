"""Tests for NormativeChunker and supporting utilities."""

from __future__ import annotations

from pathlib import Path

from localdocsai.indexing.chunker import (
    Chunk,
    NormativeChunker,
    _approx_tokens,
    _derive_doc_id,
    _detect_boundary,
)
from localdocsai.parsers.base import PageContent, ParsedDocument

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_doc(
    text: str, filename: str = "test.pdf", norm_codes: list[str] | None = None
) -> ParsedDocument:
    """Build a minimal ParsedDocument from raw text."""
    return ParsedDocument(
        source_path=Path(filename),
        doc_type="pdf",
        title=Path(filename).stem,
        pages=[PageContent(page_number=1, text=text)],
        norm_codes=norm_codes or [],
    )


NORMATIVE_TEXT = """\
1. OBJETO
La presente norma establece los requisitos para la distribución de gas natural.
Aplica a todos los concesionarios del servicio.

2. ALCANCE
Es aplicable en todo el territorio nacional.

Artículo 1°. Definiciones.
Para los efectos de la presente norma se entiende por:
a) Concesionario: la empresa que opera la red de distribución.
b) Usuario: la persona natural o jurídica que recibe el servicio.

Artículo 2°. Requisitos generales.
Todo concesionario debe cumplir con los siguientes requisitos técnicos:
- Presión mínima de suministro: 10 mbar.
- Caudal máximo permitido: 50 m3/h.
"""

LONG_ARTICLE_TEXT = "Artículo 3°. Obligaciones.\n" + ("Esta es una obligación importante. " * 120)


# ---------------------------------------------------------------------------
# _detect_boundary
# ---------------------------------------------------------------------------


class TestDetectBoundary:
    def test_article_standard(self) -> None:
        assert _detect_boundary("Artículo 5°. Objeto.") == 2

    def test_article_no_tilde(self) -> None:
        assert _detect_boundary("Articulo 5°. Objeto.") == 2

    def test_article_abbreviated(self) -> None:
        assert _detect_boundary("Art. 5°. Objeto.") == 2

    def test_article_caps(self) -> None:
        assert _detect_boundary("ARTÍCULO 5") == 2

    def test_section_level1(self) -> None:
        assert _detect_boundary("1. OBJETO") == 1

    def test_section_level2(self) -> None:
        assert _detect_boundary("1.1 Alcance") == 2

    def test_section_level3(self) -> None:
        assert _detect_boundary("1.1.1 Definiciones específicas") == 3

    def test_annex(self) -> None:
        assert _detect_boundary("ANEXO N° 1") == 0

    def test_no_boundary_mid_sentence(self) -> None:
        assert _detect_boundary("El artículo 5 establece un plazo.") is None

    def test_no_boundary_empty_line(self) -> None:
        assert _detect_boundary("") is None

    def test_no_boundary_plain_text(self) -> None:
        assert _detect_boundary("La empresa debe cumplir los requisitos.") is None


# ---------------------------------------------------------------------------
# _derive_doc_id
# ---------------------------------------------------------------------------


class TestDeriveDocId:
    def test_pdf_osinergmin(self) -> None:
        result = _derive_doc_id(Path("Osinergmin-029-2016-OS-CD.pdf"))
        assert result == "osinergmin-029-2016-os-cd"

    def test_double_extension(self) -> None:
        result = _derive_doc_id(Path("DS N° 001-2022-MINEM-EM.pdf.pdf"))
        assert "001-2022" in result
        assert "pdf" not in result

    def test_lowercase(self) -> None:
        result = _derive_doc_id(Path("MyDocument.pdf"))
        assert result == result.lower()

    def test_spaces_become_hyphens(self) -> None:
        result = _derive_doc_id(Path("My Document Name.pdf"))
        assert " " not in result
        assert "-" in result


# ---------------------------------------------------------------------------
# _approx_tokens
# ---------------------------------------------------------------------------


class TestApproxTokens:
    def test_empty_string(self) -> None:
        assert _approx_tokens("") == 1  # min 1

    def test_known_length(self) -> None:
        text = "a" * 400
        assert _approx_tokens(text) == 100


# ---------------------------------------------------------------------------
# NormativeChunker.chunk
# ---------------------------------------------------------------------------


class TestNormativeChunker:
    def test_returns_list_of_chunks(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT)
        chunks = NormativeChunker().chunk(doc)
        assert isinstance(chunks, list)
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_produces_multiple_chunks(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT)
        chunks = NormativeChunker(min_chunk_tokens=10).chunk(doc)
        assert len(chunks) >= 2

    def test_doc_id_derived_from_filename(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT, filename="Osinergmin-029-2016-OS-CD.pdf")
        chunks = NormativeChunker().chunk(doc)
        assert all(c.doc_id == "osinergmin-029-2016-os-cd" for c in chunks)

    def test_norm_code_propagated(self) -> None:
        doc = _make_doc(
            NORMATIVE_TEXT,
            norm_codes=["RCD N° 029-2016-OS/CD"],
        )
        chunks = NormativeChunker().chunk(doc)
        assert all(c.norm_code == "RCD N° 029-2016-OS/CD" for c in chunks)

    def test_chunk_index_sequential(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT)
        chunks = NormativeChunker(min_chunk_tokens=10).chunk(doc)
        indexes = [c.chunk_index for c in chunks]
        assert indexes == list(range(len(chunks)))

    def test_page_number_recorded(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT)
        chunks = NormativeChunker().chunk(doc)
        assert all(c.page == 1 for c in chunks)

    def test_section_path_populated(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT)
        chunks = NormativeChunker(min_chunk_tokens=10).chunk(doc)
        paths = [c.section_path for c in chunks if c.section_path]
        assert len(paths) > 0

    def test_article_boundary_in_section_path(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT)
        chunks = NormativeChunker(min_chunk_tokens=10).chunk(doc)
        article_chunks = [c for c in chunks if "Artículo" in c.section_path]
        assert len(article_chunks) >= 1

    def test_token_count_within_bounds(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT)
        chunks = NormativeChunker(max_tokens=800).chunk(doc)
        for chunk in chunks:
            assert chunk.token_count <= 800 * 1.1  # 10% tolerance for split granularity

    def test_long_article_force_split(self) -> None:
        # overlap_tokens=0 isolates the max_tokens check from overlap expansion
        doc = _make_doc(LONG_ARTICLE_TEXT)
        chunks = NormativeChunker(max_tokens=200, overlap_tokens=0).chunk(doc)
        assert len(chunks) >= 2
        assert all(c.token_count <= 200 * 1.1 for c in chunks)

    def test_to_dict_has_required_keys(self) -> None:
        doc = _make_doc(NORMATIVE_TEXT, norm_codes=["RCD N° 029-2016-OS/CD"])
        chunks = NormativeChunker().chunk(doc)
        required = {
            "doc_id",
            "chunk_index",
            "page",
            "section_path",
            "norm_code",
            "text",
            "token_count",
        }
        for chunk in chunks:
            assert required.issubset(chunk.to_dict().keys())

    def test_multipage_document(self) -> None:
        doc = ParsedDocument(
            source_path=Path("multi.pdf"),
            doc_type="pdf",
            title="multi",
            pages=[
                PageContent(1, "1. OBJETO\nContenido de la sección objeto."),
                PageContent(2, "Artículo 1°. Definiciones.\nTexto del artículo."),
            ],
            norm_codes=[],
        )
        chunks = NormativeChunker(min_chunk_tokens=5).chunk(doc)
        pages_seen = {c.page for c in chunks}
        assert 1 in pages_seen or 2 in pages_seen
