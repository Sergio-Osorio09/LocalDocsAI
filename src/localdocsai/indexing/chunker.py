from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from localdocsai.parsers.base import ParsedDocument
from localdocsai.utils.paths import derive_doc_id as _derive_doc_id

# ---------------------------------------------------------------------------
# Boundary patterns — ordered from most to least specific
# Each entry: (compiled pattern, hierarchy level)
#   level 0 = top (annexes)  — always starts a new chunk
#   level 1 = section        — "1. OBJETO"
#   level 2 = article/subsec — "Artículo 5°." / "1.1 Alcance"
#   level 3 = sub-subsection — "1.1.1 ..."
# ---------------------------------------------------------------------------

_BOUNDARIES: list[tuple[re.Pattern[str], int]] = [
    # Annexes: ANEXO N° / Anexo IV
    (re.compile(r"^ANEXO\s+N?[°º]?\s*\d*\b", re.IGNORECASE), 0),
    (re.compile(r"^Anexo\s+[IVX]+\b", re.IGNORECASE), 0),
    # Sub-subsections checked before subsections (more specific)
    (re.compile(r"^\d+\.\d+\.\d+[\s\t]+\S"), 3),
    # Top-level sections: "1. OBJETO" (ALL-CAPS word after number)
    (re.compile(r"^\d+\.\s+[A-ZÁÉÍÓÚÑ]{2,}"), 1),
    # Articles — three common variants in Peruvian regulations
    (re.compile(r"^Art[ií]culo\s+\d+[°º.]", re.IGNORECASE), 2),
    (re.compile(r"^ARTÍCULO\s+\d+", re.IGNORECASE), 2),
    (re.compile(r"^Art\.\s*\d+[°º.]", re.IGNORECASE), 2),
    # Subsections: "1.1 Alcance"
    (re.compile(r"^\d+\.\d+\s+[A-Za-záéíóúñÁÉÍÓÚÑ]"), 2),
]


def _detect_boundary(line: str) -> int | None:
    """Return boundary level if *line* starts a new normative unit, else None."""
    for pattern, level in _BOUNDARIES:
        if pattern.match(line):
            return level
    return None


def _approx_tokens(text: str) -> int:
    """Approximate token count: 1 token ≈ 4 characters (good enough for Spanish)."""
    return max(1, len(text) // 4)


def _split_long_lines(lines: list[str], max_chars: int) -> list[str]:
    """Break any line that exceeds *max_chars* at sentence boundaries.

    This ensures the force-split logic always has multiple lines to work with,
    even when a paragraph arrives as a single very long string.
    """
    result: list[str] = []
    for line in lines:
        if len(line) <= max_chars:
            result.append(line)
            continue
        # Split at sentence-ending punctuation followed by whitespace
        sentences = re.split(r"(?<=[.?!;])\s+", line)
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            if current_len + len(sentence) > max_chars and current:
                result.append(" ".join(current))
                current = [sentence]
                current_len = len(sentence)
            else:
                current.append(sentence)
                current_len += len(sentence) + 1
        if current:
            result.append(" ".join(current))
    return result


def _find_split_point(lines: list[str]) -> int:
    """Find the best line index to force-split a buffer that exceeded max_tokens.

    Prefers the last empty line in the upper 3/4 of the buffer so we don't
    cut in the middle of a sentence.
    """
    target = max(1, len(lines) * 3 // 4)
    for i in range(target, len(lines) // 2, -1):
        if not lines[i].strip():
            return i
    return target


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A text fragment with full normative provenance metadata.

    chunk_index is sequential within a document and becomes the SQLite primary
    key in Phase 3.
    """

    doc_id: str
    chunk_index: int
    page: int
    section_path: str
    norm_code: str
    text: str
    token_count: int
    group_tags: str = field(default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "page": self.page,
            "section_path": self.section_path,
            "norm_code": self.norm_code,
            "token_count": self.token_count,
            "group_tags": self.group_tags,
            "text": self.text,
        }


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------


class NormativeChunker:
    """Splits a ParsedDocument into Chunks that respect normative structure.

    Articles, numbered sections, and annexes are treated as hard boundaries:
    the chunker never cuts in the middle of a logical unit.  If a single unit
    exceeds max_tokens, it is split at the nearest paragraph boundary and the
    continuation is marked in section_path with "(cont.)".
    """

    def __init__(
        self,
        max_tokens: int = 800,
        overlap_tokens: int = 100,
        min_chunk_tokens: int = 50,
    ) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        """Return all chunks for *doc* in reading order."""
        doc_id = _derive_doc_id(doc.source_path)
        norm_code = doc.norm_codes[0] if doc.norm_codes else ""

        # section_stack[level] holds the header text for that hierarchy level.
        section_stack: list[str] = [""] * 4

        buffer_lines: list[str] = []
        buffer_page: int = doc.pages[0].page_number if doc.pages else 1
        overlap_text: str = ""
        chunk_index: int = 0
        chunks: list[Chunk] = []

        def emit() -> None:
            nonlocal chunk_index, overlap_text
            text = "\n".join(buffer_lines).strip()
            if not text or _approx_tokens(text) < self.min_chunk_tokens:
                return
            section_path = " > ".join(s for s in section_stack if s)
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    page=buffer_page,
                    section_path=section_path,
                    norm_code=norm_code,
                    text=text,
                    token_count=_approx_tokens(text),
                )
            )
            # Keep tail of this chunk as overlap for the next one.
            # Guard against text[-0:] == text[:] (Python semantics for n=0).
            overlap_chars = self.overlap_tokens * 4
            overlap_text = text[-overlap_chars:] if overlap_chars > 0 else ""
            chunk_index += 1

        for page in doc.pages:
            max_line_chars = self.max_tokens * 4
            for line in _split_long_lines(page.text.splitlines(), max_line_chars):
                stripped = line.strip()

                boundary_level = _detect_boundary(stripped) if stripped else None

                if boundary_level is not None:
                    current_tokens = _approx_tokens("\n".join(buffer_lines))
                    if current_tokens >= self.min_chunk_tokens:
                        emit()
                        buffer_lines = [overlap_text] if overlap_text else []
                        buffer_page = page.page_number

                    # Update section hierarchy: clear levels below this one
                    section_stack[boundary_level] = stripped[:80]
                    for i in range(boundary_level + 1, len(section_stack)):
                        section_stack[i] = ""

                buffer_lines.append(line)

                # Force-split if buffer exceeds max_tokens
                if _approx_tokens("\n".join(buffer_lines)) >= self.max_tokens:
                    split_at = _find_split_point(buffer_lines)
                    head, tail = buffer_lines[:split_at], buffer_lines[split_at:]
                    buffer_lines = head
                    emit()
                    # Mark continuation in section path
                    if section_stack[boundary_level or 0]:
                        level = boundary_level or 0
                        if not section_stack[level].endswith("(cont.)"):
                            section_stack[level] += " (cont.)"
                    buffer_lines = ([overlap_text] if overlap_text else []) + tail
                    buffer_page = page.page_number

        emit()  # flush remaining buffer
        return chunks
