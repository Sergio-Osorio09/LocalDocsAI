from pathlib import Path

from .base import BaseParser, PageContent, ParsedDocument, extract_norm_codes
from .docx_parser import DocxParser
from .pdf_parser import PdfParser
from .xlsx_parser import XlsxParser

_REGISTRY: list[type[BaseParser]] = [PdfParser, DocxParser, XlsxParser]


def get_parser(path: Path) -> BaseParser:
    """Return the appropriate parser for *path*, or raise ValueError."""
    for parser_cls in _REGISTRY:
        if parser_cls.supports(path):
            return parser_cls()
    raise ValueError(
        f"No parser available for extension {path.suffix!r}. "
        f"Supported: .pdf, .docx, .xlsx, .xlsm"
    )


__all__ = [
    "BaseParser",
    "DocxParser",
    "PageContent",
    "ParsedDocument",
    "PdfParser",
    "XlsxParser",
    "extract_norm_codes",
    "get_parser",
]
