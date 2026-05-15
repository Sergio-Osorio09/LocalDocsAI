from __future__ import annotations

import re
from dataclasses import dataclass, field

from localdocsai.retrieval.retriever import RetrievedChunk

_CITE_RE = re.compile(r"\[(\d+)\]")


@dataclass
class ValidationResult:
    is_valid: bool
    cited_indices: list[int] = field(default_factory=list)
    invalid_indices: list[int] = field(default_factory=list)


def validate_citations(response: str, num_chunks: int) -> ValidationResult:
    """Check that every [N] in *response* is a valid 1-based chunk index."""
    cited = [int(m) for m in _CITE_RE.findall(response)]
    invalid = [n for n in cited if n < 1 or n > num_chunks]
    return ValidationResult(
        is_valid=len(invalid) == 0,
        cited_indices=cited,
        invalid_indices=invalid,
    )


def format_response(response: str, chunks: list[RetrievedChunk]) -> str:
    """Replace [N] markers with human-readable citation strings.

    Example: [2] → (RCD N° 029-2016-OS/CD, Artículo 5°., p.12)
    """

    def _replace(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        if 1 <= idx <= len(chunks):
            chunk = chunks[idx - 1]
            parts: list[str] = []
            if chunk.norm_code:
                parts.append(chunk.norm_code)
            if chunk.section_path:
                parts.append(chunk.section_path.split(" > ")[-1])
            parts.append(f"p.{chunk.page}")
            return f"({', '.join(parts)})"
        return m.group(0)

    return _CITE_RE.sub(_replace, response)
