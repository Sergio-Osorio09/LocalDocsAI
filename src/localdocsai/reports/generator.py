"""Heuristic auto-fill for report template fields from conversation messages."""

from __future__ import annotations

from datetime import date

from localdocsai.reports.template import TemplateField


def autofill(
    fields: list[TemplateField],
    messages: list[dict[str, str]],
    chat_title: str = "",
) -> list[TemplateField]:
    """Return *fields* with `.value` populated from conversation heuristics.

    Each field is filled based on its semantic_type; unknown types are left empty
    so the user can fill them manually in the editor dialog.

    *messages* must be a list of dicts with keys "role" ("user"|"assistant") and "text".
    """
    user_texts = [m["text"] for m in messages if m.get("role") == "user"]
    assistant_texts = [m["text"] for m in messages if m.get("role") == "assistant"]

    filled: list[TemplateField] = []
    for field in fields:
        value = _fill_field(field.semantic_type, user_texts, assistant_texts, chat_title)
        filled.append(TemplateField(
            paragraph_idx=field.paragraph_idx,
            pattern=field.pattern,
            context=field.context,
            label=field.label,
            semantic_type=field.semantic_type,
            value=value,
        ))
    return filled


def _fill_field(
    sem_type: str,
    user_texts: list[str],
    assistant_texts: list[str],
    chat_title: str,
) -> str:
    if sem_type == "date":
        return date.today().strftime("%d/%m/%Y")
    if sem_type == "title":
        return chat_title
    if sem_type == "topic":
        return user_texts[0][:120] if user_texts else ""
    if sem_type == "objective":
        return user_texts[0] if user_texts else ""
    if sem_type == "synthesis":
        return _build_synthesis(user_texts, assistant_texts)
    return ""


def _build_synthesis(user_texts: list[str], assistant_texts: list[str]) -> str:
    parts: list[str] = []
    for i, (q, a) in enumerate(zip(user_texts, assistant_texts, strict=False), 1):
        parts.append(f"Consulta {i}:\n{q}\n\nRespuesta:\n{a}")
    return "\n\n---\n\n".join(parts)
