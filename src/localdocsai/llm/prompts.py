from __future__ import annotations

from localdocsai.retrieval.retriever import RetrievedChunk

_SYSTEM_PROMPT = (
    "Eres un asistente especializado en documentos normativos y técnicos. "
    "Tu función es responder preguntas basándote EXCLUSIVAMENTE en los fragmentos "
    "de documentos que se te proporcionan.\n\n"
    "Reglas obligatorias:\n"
    "1. Cita SOLO los fragmentos proporcionados usando el número entre corchetes: [1], [2], etc.\n"
    "2. Si la respuesta no está en los fragmentos, indícalo explícitamente. "
    "No inventes ni añadas información externa.\n"
    "3. Acompaña cada afirmación relevante con su cita correspondiente.\n"
    "4. Responde siempre en español."
)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks as a numbered context block for the prompt."""
    lines: list[str] = ["Fragmentos de documentos relevantes:\n"]
    for i, chunk in enumerate(chunks, 1):
        header_parts = [f"[{i}]"]
        if chunk.norm_code:
            header_parts.append(chunk.norm_code)
        if chunk.section_path:
            header_parts.append(chunk.section_path)
        header_parts.append(f"p.{chunk.page}")
        lines.append(" | ".join(header_parts))
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines)


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> tuple[str, str]:
    """Return *(system_prompt, user_message)* ready to pass to the LLM."""
    context = build_context_block(chunks)
    user_message = f"{context}\nPregunta: {question}"
    return _SYSTEM_PROMPT, user_message
