from __future__ import annotations

from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from .base import BaseParser, PageContent, ParsedDocument, extract_norm_codes

_SUPPORTED_EXTENSIONS = {".pdf"}

# Vertical zones (fraction of page height) considered header/footer territory.
# Text whose bounding box starts above _HEADER_ZONE or ends below _FOOTER_ZONE
# is a candidate for removal if it also repeats across many pages.
_HEADER_ZONE = 0.08
_FOOTER_ZONE = 0.92

# A text block is treated as a repeating header/footer if it appears on this
# fraction of total pages (or at least 2 pages).
_REPEAT_THRESHOLD = 0.4


class PdfParser(BaseParser):
    """Parser for PDF documents using PyMuPDF (fitz)."""

    @classmethod
    def supports(cls, path: Path) -> bool:
        return path.suffix.lower() in _SUPPORTED_EXTENSIONS

    def parse(self, path: Path) -> ParsedDocument:
        doc: fitz.Document = fitz.open(str(path))
        try:
            repeating = self._detect_repeating_text(doc)
            pages = [self._extract_page(page, repeating) for page in doc]
        finally:
            doc.close()

        full_text = "\n\n".join(p.text for p in pages)
        # Detect norm codes from body text AND filename (filenames like
        # "Osinergmin-029-2016-OS-CD.pdf" already encode the code)
        norm_codes = sorted(set(extract_norm_codes(full_text)) | set(extract_norm_codes(path.stem)))

        return ParsedDocument(
            source_path=path,
            doc_type="pdf",
            title=path.stem,
            pages=pages,
            norm_codes=norm_codes,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_page(self, page: fitz.Page, repeating_text: set[str]) -> PageContent:
        """Extract cleaned text from a single page, removing headers/footers."""
        page_height = page.rect.height
        lines: list[str] = []

        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = block
            text = text.strip()
            if not text:
                continue
            # Skip blocks in header/footer zones
            if y0 < page_height * _HEADER_ZONE:
                continue
            if y1 > page_height * _FOOTER_ZONE:
                continue
            # Skip blocks identified as repeating across pages
            if text in repeating_text:
                continue
            lines.append(text)

        return PageContent(
            page_number=page.number + 1,  # fitz uses 0-indexed pages
            text="\n".join(lines),
        )

    def _detect_repeating_text(self, doc: fitz.Document) -> set[str]:
        """Find text blocks that appear on more than _REPEAT_THRESHOLD of pages.

        These are almost always headers, footers, watermarks, or page numbers
        that add noise to the extracted text.
        """
        total_pages = len(doc)
        if total_pages < 3:
            return set()

        counts: Counter[str] = Counter()
        threshold = max(2, int(total_pages * _REPEAT_THRESHOLD))

        for page in doc:
            page_height = page.rect.height
            seen_this_page: set[str] = set()

            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text, *_ = block
                text = text.strip()
                if not text or text in seen_this_page:
                    continue
                # Only consider blocks in header/footer zones as candidates
                in_header = y0 < page_height * _HEADER_ZONE
                in_footer = y1 > page_height * _FOOTER_ZONE
                if in_header or in_footer:
                    seen_this_page.add(text)
                    counts[text] += 1

        return {text for text, count in counts.items() if count >= threshold}
