"""Tests for base data structures and norm code extraction."""

from __future__ import annotations

from pathlib import Path

from localdocsai.parsers.base import PageContent, ParsedDocument, extract_norm_codes


class TestExtractNormCodes:
    def test_rcd_standard(self) -> None:
        text = "Según la RCD N° 029-2016-OS/CD, el plazo es de 30 días."
        codes = extract_norm_codes(text)
        assert any("029-2016" in c for c in codes)

    def test_decreto_supremo(self) -> None:
        text = "El D.S. N° 021-2021-MINEM-EM regula las instalaciones."
        codes = extract_norm_codes(text)
        assert any("021-2021" in c for c in codes)

    def test_ds_without_dots(self) -> None:
        text = "DS N° 001-2022-MINEM-EM aprobó el reglamento."
        codes = extract_norm_codes(text)
        assert any("001-2022" in c for c in codes)

    def test_osinergmin_filename_style(self) -> None:
        text = "Ver Osinergmin-162-2019-OS-CD para más detalles."
        codes = extract_norm_codes(text)
        assert any("162-2019" in c for c in codes)

    def test_no_false_positives(self) -> None:
        text = "El artículo 5 establece un plazo de 90 días hábiles."
        assert extract_norm_codes(text) == []

    def test_deduplication(self) -> None:
        text = "RCD N° 029-2016-OS/CD y nuevamente RCD N° 029-2016-OS/CD"
        codes = extract_norm_codes(text)
        assert len(codes) == 1

    def test_multiple_codes(self) -> None:
        text = (
            "La RCD N° 029-2016-OS/CD y el D.S. N° 021-2021-MINEM-EM " "son las normas aplicables."
        )
        codes = extract_norm_codes(text)
        assert len(codes) == 2


class TestParsedDocument:
    def test_full_text_joins_pages(self) -> None:
        doc = ParsedDocument(
            source_path=Path("test.pdf"),
            doc_type="pdf",
            title="test",
            pages=[
                PageContent(page_number=1, text="Página uno"),
                PageContent(page_number=2, text="Página dos"),
            ],
        )
        assert "Página uno" in doc.full_text
        assert "Página dos" in doc.full_text

    def test_page_count(self) -> None:
        doc = ParsedDocument(
            source_path=Path("test.pdf"),
            doc_type="pdf",
            title="test",
            pages=[PageContent(1, "a"), PageContent(2, "b"), PageContent(3, "c")],
        )
        assert doc.page_count == 3

    def test_to_dict_structure(self) -> None:
        doc = ParsedDocument(
            source_path=Path("test.pdf"),
            doc_type="pdf",
            title="test",
            pages=[PageContent(1, "texto")],
            norm_codes=["RCD N° 029-2016-OS/CD"],
        )
        d = doc.to_dict()
        assert d["doc_type"] == "pdf"
        assert d["page_count"] == 1
        assert d["norm_codes"] == ["RCD N° 029-2016-OS/CD"]
        assert d["pages"][0]["page_number"] == 1

    def test_full_text_skips_empty_pages(self) -> None:
        doc = ParsedDocument(
            source_path=Path("test.pdf"),
            doc_type="pdf",
            title="test",
            pages=[
                PageContent(1, "Contenido"),
                PageContent(2, "   "),
                PageContent(3, "Más contenido"),
            ],
        )
        assert "   " not in doc.full_text
