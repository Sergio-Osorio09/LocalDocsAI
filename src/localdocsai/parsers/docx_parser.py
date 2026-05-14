from __future__ import annotations

from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from .base import BaseParser, PageContent, ParsedDocument, extract_norm_codes

_SUPPORTED_EXTENSIONS = {".docx"}


class DocxParser(BaseParser):
    """Parser for Word documents (.docx) using python-docx."""

    @classmethod
    def supports(cls, path: Path) -> bool:
        return path.suffix.lower() in _SUPPORTED_EXTENSIONS

    def parse(self, path: Path) -> ParsedDocument:
        document = docx.Document(str(path))
        lines: list[str] = []

        for element in document.element.body:
            tag = element.tag.split("}")[-1]  # strip XML namespace prefix

            if tag == "p":
                para = Paragraph(element, document)
                text = para.text.strip()
                if not text:
                    continue
                style_name = para.style.name if para.style else ""
                if style_name.startswith("Heading"):
                    # Prefix headings with markdown-style markers to preserve
                    # document structure for the downstream chunker
                    try:
                        level = int(style_name.split()[-1])
                    except (ValueError, IndexError):
                        level = 1
                    lines.append(f"{'#' * level} {text}")
                else:
                    lines.append(text)

            elif tag == "tbl":
                table = Table(element, document)
                lines.extend(self._table_to_lines(table))

        full_text = "\n".join(lines)
        norm_codes = sorted(set(extract_norm_codes(full_text)) | set(extract_norm_codes(path.stem)))

        return ParsedDocument(
            source_path=path,
            doc_type="docx",
            title=path.stem,
            # DOCX has no native page numbering accessible via python-docx;
            # treat the whole document as a single logical page.
            pages=[PageContent(page_number=1, text=full_text)],
            norm_codes=norm_codes,
        )

    def _table_to_lines(self, table: Table) -> list[str]:
        lines: list[str] = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            row_text = " | ".join(c for c in cells if c)
            if row_text:
                lines.append(row_text)
        return lines
