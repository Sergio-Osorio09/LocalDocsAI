from __future__ import annotations

from localdocsai.retrieval.retriever import RetrievedChunk

_SYSTEM_PROMPT = (
    "Eres un asistente experto en normativa técnica peruana de Osinergmin. "
    "Se te proporcionan fragmentos numerados de documentos oficiales. "
    "Tu tarea es responder la pregunta del usuario usando ÚNICAMENTE esos fragmentos.\n\n"
    "INSTRUCCIONES:\n"
    "- Cita el número del fragmento entre corchetes después de cada afirmación. "
    "Ejemplo: 'El concesionario debe presentar informes mensuales [2].'\n"
    "- Si varios fragmentos hablan del tema, úsalos todos y cita cada uno.\n"
    "- Aunque los fragmentos no respondan perfectamente, extrae y resume "
    "toda información parcialmente relacionada con la pregunta.\n"
    "- Organiza la respuesta en puntos numerados cuando haya múltiples requisitos.\n"
    "- Responde siempre en español.\n"
    "- NUNCA respondas que no tienes información si los fragmentos contienen "
    "algo relacionado, aunque sea parcialmente."
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
