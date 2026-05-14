"""Tests for XlsxParser."""

from __future__ import annotations

from pathlib import Path

from localdocsai.parsers.xlsx_parser import XlsxParser


class TestXlsxParserSupports:
    def test_accepts_xlsx(self, tmp_path: Path) -> None:
        assert XlsxParser.supports(tmp_path / "data.xlsx")

    def test_accepts_xlsm(self, tmp_path: Path) -> None:
        assert XlsxParser.supports(tmp_path / "data.xlsm")

    def test_rejects_pdf(self, tmp_path: Path) -> None:
        assert not XlsxParser.supports(tmp_path / "data.pdf")


class TestXlsxParserParse:
    def test_returns_parsed_document(self, sample_xlsx: Path) -> None:
        result = XlsxParser().parse(sample_xlsx)
        assert result.doc_type == "xlsx"

    def test_one_page_per_sheet(self, sample_xlsx: Path) -> None:
        result = XlsxParser().parse(sample_xlsx)
        assert result.page_count == 2

    def test_page_numbers_are_sequential(self, sample_xlsx: Path) -> None:
        result = XlsxParser().parse(sample_xlsx)
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2

    def test_sheet_name_in_text(self, sample_xlsx: Path) -> None:
        result = XlsxParser().parse(sample_xlsx)
        assert "Hoja1" in result.full_text
        assert "Hoja2" in result.full_text

    def test_cell_values_extracted(self, sample_xlsx: Path) -> None:
        result = XlsxParser().parse(sample_xlsx)
        assert "Cobertura" in result.full_text
        assert "85%" in result.full_text

    def test_pipe_separated_rows(self, sample_xlsx: Path) -> None:
        result = XlsxParser().parse(sample_xlsx)
        assert "|" in result.full_text

    def test_detects_norm_code_in_cell(self, sample_xlsx: Path) -> None:
        result = XlsxParser().parse(sample_xlsx)
        # "Osinergmin-029-2016-OS-CD" is a cell value in the fixture
        assert any("029-2016" in c for c in result.norm_codes)
