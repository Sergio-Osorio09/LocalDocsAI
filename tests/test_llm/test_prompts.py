"""Tests for PromptBuilder — no ML deps required."""

from __future__ import annotations

from localdocsai.llm.prompts import _SYSTEM_PROMPT, build_context_block, build_prompt
from localdocsai.retrieval.retriever import RetrievedChunk


def _chunk(
    idx: int,
    norm_code: str = "RCD N° 001-2020",
    section_path: str = "Artículo 1°.",
    page: int = 5,
    text: str = "Texto de prueba.",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=idx,
        doc_id="test-doc",
        score=0.9,
        text=text,
        page=page,
        section_path=section_path,
        norm_code=norm_code,
    )


class TestBuildContextBlock:
    def test_includes_all_chunks(self) -> None:
        chunks = [_chunk(i) for i in range(3)]
        block = build_context_block(chunks)
        assert "[1]" in block
        assert "[2]" in block
        assert "[3]" in block

    def test_includes_chunk_text(self) -> None:
        chunks = [_chunk(1, text="Contenido específico del artículo.")]
        block = build_context_block(chunks)
        assert "Contenido específico del artículo." in block

    def test_includes_norm_code(self) -> None:
        chunks = [_chunk(1, norm_code="RCD N° 029-2016-OS/CD")]
        block = build_context_block(chunks)
        assert "RCD N° 029-2016-OS/CD" in block

    def test_includes_section_path(self) -> None:
        chunks = [_chunk(1, section_path="1. OBJETO > 1.1 Alcance")]
        block = build_context_block(chunks)
        assert "1. OBJETO > 1.1 Alcance" in block

    def test_includes_page(self) -> None:
        chunks = [_chunk(1, page=42)]
        block = build_context_block(chunks)
        assert "p.42" in block

    def test_empty_norm_code_not_added(self) -> None:
        chunks = [_chunk(1, norm_code="")]
        block = build_context_block(chunks)
        # Should not have double separators from missing norm_code
        assert "| |" not in block

    def test_empty_section_path_not_added(self) -> None:
        chunks = [_chunk(1, section_path="")]
        block = build_context_block(chunks)
        assert "| p." in block  # page still present


class TestBuildPrompt:
    def test_returns_tuple(self) -> None:
        result = build_prompt("¿Qué norma regula X?", [_chunk(1)])
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_prompt_constant(self) -> None:
        system, _ = build_prompt("pregunta", [_chunk(1)])
        assert system == _SYSTEM_PROMPT

    def test_user_message_contains_question(self) -> None:
        question = "¿Cuál es el límite de odorización?"
        _, user_msg = build_prompt(question, [_chunk(1)])
        assert question in user_msg

    def test_user_message_contains_context(self) -> None:
        chunks = [_chunk(1, text="Texto del artículo primero.")]
        _, user_msg = build_prompt("pregunta", chunks)
        assert "Texto del artículo primero." in user_msg

    def test_system_prompt_mentions_citation_rule(self) -> None:
        assert "[1]" in _SYSTEM_PROMPT or "corchetes" in _SYSTEM_PROMPT

    def test_system_prompt_in_spanish(self) -> None:
        assert "español" in _SYSTEM_PROMPT.lower()
