from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Normative code patterns — Peruvian regulations (Osinergmin domain)
# ---------------------------------------------------------------------------

_NORM_PATTERNS: list[re.Pattern[str]] = [
    # RCD N° 029-2016-OS/CD  (Resolución de Consejo Directivo)
    re.compile(r"RCD\s+N[°º]?\s*\d{3}[-–]\d{4}[-–]OS/CD", re.IGNORECASE),
    # Resolución de Consejo Directivo N° 253-2021-OS/CD
    re.compile(
        r"Resoluci[oó]n\s+de\s+Consejo\s+Directivo\s+N[°º]?\s*\d{3}[-–]\d{4}[-–]OS/CD",
        re.IGNORECASE,
    ),
    # Osinergmin-029-2016-OS-CD  (from filenames and body text)
    re.compile(r"Osinergmin[-\s]\d{3}[-–]\d{4}[-–]OS[-/]CD", re.IGNORECASE),
    # D.S. N° 021-2021-MINEM-EM  (Decreto Supremo)
    re.compile(
        r"D\.S\.\s+N[°º]?\s*\d{3}[-–]\d{4}[-–][A-Z]+(?:[-/][A-Z]+)?",
        re.IGNORECASE,
    ),
    # DS N° 001-2022-MINEM/EM  (variant without dots)
    re.compile(
        r"DS\s+N[°º]?\s*\d{3}[-–]\d{4}[-–][A-Z]+(?:[-/][A-Z]+)?",
        re.IGNORECASE,
    ),
]


def extract_norm_codes(text: str) -> list[str]:
    """Return deduplicated normative codes found in *text*, sorted."""
    found: set[str] = set()
    for pattern in _NORM_PATTERNS:
        for match in pattern.finditer(text):
            # Collapse internal whitespace so variants match as one code
            code = " ".join(match.group().split())
            found.add(code)
    return sorted(found)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PageContent:
    """Text extracted from a single page (PDF) or sheet (XLSX)."""

    page_number: int  # 1-indexed
    text: str


@dataclass
class ParsedDocument:
    """Structured output from any parser."""

    source_path: Path
    doc_type: str  # "pdf" | "docx" | "xlsx"
    title: str
    pages: list[PageContent]
    norm_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "doc_type": self.doc_type,
            "title": self.title,
            "page_count": self.page_count,
            "norm_codes": self.norm_codes,
            "metadata": self.metadata,
            "pages": [{"page_number": p.page_number, "text": p.text} for p in self.pages],
        }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseParser(ABC):
    """Contract that all document parsers must implement."""

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """Parse *path* and return structured content with metadata."""
        ...

    @classmethod
    @abstractmethod
    def supports(cls, path: Path) -> bool:
        """Return True if this parser handles the file at *path*."""
        ...
