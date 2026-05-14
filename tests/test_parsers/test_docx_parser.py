"""Tests for DocxParser."""

from __future__ import annotations

from pathlib import Path

from localdocsai.parsers.docx_parser import DocxParser


class TestDocxParserSupports:
    def test_accepts_docx(self, tmp_path: Path) -> None:
        assert DocxParser.supports(tmp_path / "doc.docx")

    def test_rejects_pdf(self, tmp_path: Path) -> None:
        assert not DocxParser.supports(tmp_path / "doc.pdf")

    def test_rejects_xlsx(self, tmp_path: Path) -> None:
        assert not DocxParser.supports(tmp_path / "doc.xlsx")


class TestDocxParserParse:
    def test_returns_parsed_document(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert result.doc_type == "docx"

    def test_single_page(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert result.page_count == 1

    def test_extracts_heading(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert "Informe de prueba" in result.full_text

    def test_heading_has_markdown_prefix(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert "# Informe de prueba" in result.full_text

    def test_extracts_paragraph_text(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert "requisitos técnicos" in result.full_text

    def test_extracts_table_rows(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert "Norma" in result.full_text
        assert "Vigente" in result.full_text

    def test_detects_norm_code_from_body(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert any("021-2021" in c for c in result.norm_codes)

    def test_detects_norm_code_from_table(self, sample_docx: Path) -> None:
        result = DocxParser().parse(sample_docx)
        assert any("029-2016" in c for c in result.norm_codes)
