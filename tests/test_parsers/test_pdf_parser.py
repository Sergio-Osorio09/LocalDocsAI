"""Tests for PdfParser."""

from __future__ import annotations

from pathlib import Path

from localdocsai.parsers.pdf_parser import PdfParser


class TestPdfParserSupports:
    def test_accepts_pdf(self, tmp_path: Path) -> None:
        assert PdfParser.supports(tmp_path / "doc.pdf")

    def test_rejects_docx(self, tmp_path: Path) -> None:
        assert not PdfParser.supports(tmp_path / "doc.docx")

    def test_case_insensitive(self, tmp_path: Path) -> None:
        assert PdfParser.supports(tmp_path / "DOC.PDF")


class TestPdfParserParse:
    def test_returns_parsed_document(self, sample_pdf: Path) -> None:
        result = PdfParser().parse(sample_pdf)
        assert result.doc_type == "pdf"
        assert result.source_path == sample_pdf

    def test_page_count(self, sample_pdf: Path) -> None:
        result = PdfParser().parse(sample_pdf)
        assert result.page_count == 2

    def test_pages_are_one_indexed(self, sample_pdf: Path) -> None:
        result = PdfParser().parse(sample_pdf)
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2

    def test_extracts_body_text(self, sample_pdf: Path) -> None:
        result = PdfParser().parse(sample_pdf)
        full = result.full_text
        assert "Artículo 1" in full
        assert "Artículo 2" in full

    def test_detects_norm_code_from_filename(self, sample_pdf: Path) -> None:
        result = PdfParser().parse(sample_pdf)
        assert any("029-2016" in c for c in result.norm_codes)

    def test_detects_norm_code_from_body(self, sample_pdf: Path) -> None:
        result = PdfParser().parse(sample_pdf)
        assert any("029-2016" in c for c in result.norm_codes)

    def test_title_is_filename_stem(self, sample_pdf: Path) -> None:
        result = PdfParser().parse(sample_pdf)
        assert result.title == sample_pdf.stem
