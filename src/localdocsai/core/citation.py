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
    """Return the response with [N] markers kept as-is.

    The UI's markdown renderer converts [N] into styled clickable badges.
    Full citation details (document name, page) are shown in the sources panel.
    """
    return response
