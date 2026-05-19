from __future__ import annotations

from localdocsai.retrieval.retriever import RetrievedChunk

_SYSTEM_PROMPT = (
    "Eres un asistente experto en normativa técnica peruana de Osinergmin. "
    "Se te proporcionan fragmentos numerados de documentos oficiales. "
    "Tu tarea es responder la pregunta del usuario usando ÚNICAMENTE esos fragmentos.\n\n"
    "═══ REGLA OBLIGATORIA DE CITAS ═══\n"
    "TODA afirmación o ítem de tu respuesta DEBE terminar con uno o más "
    "marcadores de cita del tipo [N], donde N es el número exacto del "
    "fragmento de donde sacaste esa información. Sin excepción.\n\n"
    "Cuando un punto está respaldado por varios fragmentos, encadénalos: "
    "[2][5] o [1][3][7].\n\n"
    "Si listas varios puntos en una enumeración, cada punto necesita su "
    "propia cita al final — no se admite una cita única al final del bloque.\n\n"
    "═══ EJEMPLOS ═══\n"
    "✓ CORRECTO:\n"
    "   El concesionario debe presentar informes mensuales [2].\n"
    "   Las sanciones administrativas incluyen multas [1][4] y suspensión "
    "de actividades [4].\n"
    "   Empresas obligadas a cumplir:\n"
    "   1. Cálidda [3].\n"
    "   2. Contugas [3][5].\n"
    "   3. Gas Natural Fenosa [5].\n\n"
    "✗ INCORRECTO (sin citas — NUNCA hagas esto):\n"
    "   El concesionario debe presentar informes mensuales.\n"
    "   Empresas obligadas a cumplir: 1. Cálidda. 2. Contugas.\n\n"
    "═══ OTRAS REGLAS ═══\n"
    "- Si los fragmentos no tienen información sobre la pregunta, di "
    "'No se encontró información sobre X en los fragmentos disponibles.' — "
    "no inventes nada.\n"
    "- Aunque los fragmentos respondan parcialmente, úsalos y cita "
    "fielmente lo que sí cubren.\n"
    "- Organiza la respuesta con encabezados o listas numeradas cuando "
    "haya múltiples requisitos.\n"
    "- Responde siempre en español, en tono técnico y conciso."
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
