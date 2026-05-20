from __future__ import annotations

import re
from dataclasses import dataclass, field

from localdocsai.retrieval.retriever import RetrievedChunk

_CITE_RE = re.compile(r"\[(\d+)\]")
_WORD_RE = re.compile(r"[a-záéíóúñ]{4,}", re.IGNORECASE)

# Spanish stopwords kept short — only the highest-frequency ones that would
# otherwise dominate the word overlap signal. Length-4+ filter handles most
# noise already.
_STOPWORDS = frozenset(
    {
        "para", "como", "donde", "cuando", "porque", "pero", "este", "esta",
        "estos", "estas", "esto", "todo", "toda", "todos", "todas", "otro",
        "otra", "otros", "otras", "sobre", "entre", "tras", "según", "segun",
        "desde", "hasta", "hacia", "ante", "bajo", "sino", "aunque", "ya",
        "que", "los", "las", "una", "uno", "unos", "unas", "del", "con",
        "por", "más", "mas", "muy", "ser", "son", "está", "esta", "están",
        "estan", "fue", "fueron", "han", "haber", "tiene", "tienen",
    }
)


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


def _tokens(text: str) -> set[str]:
    """Return the set of content-bearing lowercase tokens in *text*."""
    return {w.lower() for w in _WORD_RE.findall(text) if w.lower() not in _STOPWORDS}


def _best_chunk_for_sentence(
    sentence: str, chunks: list[RetrievedChunk], min_overlap: int = 2
) -> int | None:
    """Return the 1-based index of the chunk whose text overlaps most with
    *sentence* (by content-word intersection). None if no chunk meets the
    minimum overlap threshold so we don't append spurious citations."""
    sent_tokens = _tokens(sentence)
    if not sent_tokens:
        return None
    best_n: int | None = None
    best_score = 0
    for i, chunk in enumerate(chunks, 1):
        overlap = len(sent_tokens & _tokens(chunk.text))
        if overlap > best_score:
            best_score = overlap
            best_n = i
    return best_n if best_score >= min_overlap else None


def _enrich_with_per_sentence_citations(
    response: str, chunks: list[RetrievedChunk]
) -> str:
    """Append [N] to sentences that lack a citation, picking the chunk with
    the highest word overlap. Sentences that already have one, very short
    fragments, and headings ('**Bold:**') are left untouched."""
    if not chunks:
        return response

    out_lines: list[str] = []
    for line in response.split("\n"):
        stripped_line = line.rstrip()
        if not stripped_line.strip():
            out_lines.append(line)
            continue

        # Skip pure markdown headings or bare label rows; they're structural.
        if stripped_line.strip().startswith("#"):
            out_lines.append(line)
            continue

        # Split into sentences while keeping any leading whitespace / bullet.
        leading_ws = line[: len(line) - len(line.lstrip())]
        body = line[len(leading_ws):]

        # Numbered/bullet markers like "1. ", "- ", "* " are kept as prefix.
        prefix_match = re.match(r"^(\d+\.\s+|[-*]\s+)", body)
        prefix = prefix_match.group(0) if prefix_match else ""
        body = body[len(prefix):]

        sentences = re.split(r"(?<=[.!?])\s+", body)
        new_sentences: list[str] = []
        for sent in sentences:
            if not sent.strip():
                new_sentences.append(sent)
                continue
            if _CITE_RE.search(sent):
                new_sentences.append(sent)
                continue
            if len(_tokens(sent)) < 3:
                # Too short to attribute reliably — leave it alone.
                new_sentences.append(sent)
                continue
            best = _best_chunk_for_sentence(sent, chunks)
            if best is None:
                new_sentences.append(sent)
                continue
            # Insert citation right before the trailing punctuation if any.
            trailing = ""
            core = sent.rstrip()
            if core and core[-1] in ".!?":
                trailing = core[-1]
                core = core[:-1].rstrip()
            new_sentences.append(f"{core} [{best}]{trailing}")
        out_lines.append(leading_ws + prefix + " ".join(new_sentences))

    return "\n".join(out_lines)


def format_response(response: str, chunks: list[RetrievedChunk]) -> str:
    """Return the response with [N] markers kept as-is, then ensure every
    sentence carries a citation.

    Two-step process:
      1. Walk every line of the response and, for each sentence that lacks
         a [N] marker, append the chunk number whose text has the highest
         word overlap with the sentence (cf. _enrich_with_per_sentence_citations).
      2. If after step 1 the response still has zero citations — which can
         happen for very generic refusals or pleasantries — append a
         trailing 'Fuentes consultadas' line listing every chunk so the
         user can still click into the sources panel.
    """
    if not chunks:
        return response

    enriched = _enrich_with_per_sentence_citations(response, chunks)

    if _CITE_RE.search(enriched):
        return enriched

    fuentes = " ".join(f"[{i}]" for i in range(1, len(chunks) + 1))
    return f"{enriched.rstrip()}\n\n**Fuentes consultadas:** {fuentes}"
