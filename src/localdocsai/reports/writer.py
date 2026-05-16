"""High-level report writer — generates .docx from a filled template or plain conversation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from localdocsai.reports.template import TemplateField, fill_and_save


def write_docx(
    template_path: Path,
    fields: list[TemplateField],
    output_path: Path,
) -> None:
    """Fill *template_path* with *fields* values and save to *output_path*."""
    fill_and_save(template_path, fields, output_path)


def write_conversation_docx(
    messages: list[dict[str, Any]],
    output_path: Path,
    title: str = "Conversación",
) -> None:
    """Export *messages* as a plain Word document without a template.

    Each message is rendered as a labelled paragraph: Q: / R: prefixes,
    followed by the message text.  Sources are listed as footnotes per answer.
    """
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = Document()

    # Title
    heading = doc.add_heading(title, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT

    for msg in messages:
        role = msg.get("role", "")
        text = msg.get("text", "")

        if role == "user":
            p = doc.add_paragraph()
            run = p.add_run("Pregunta: ")
            run.bold = True
            run.font.color.rgb = RGBColor(0x1A, 0x73, 0xE8)
            p.add_run(text)
        else:
            p = doc.add_paragraph()
            run = p.add_run("Respuesta: ")
            run.bold = True
            run.font.color.rgb = RGBColor(0x0F, 0x9D, 0x58)
            p.add_run(text)

            sources = msg.get("sources", [])
            if sources:
                sp = doc.add_paragraph()
                sp.paragraph_format.left_indent = Pt(20)
                src_run = sp.add_run("Fuentes: ")
                src_run.bold = True
                src_run.font.size = Pt(9)
                parts = []
                for s in sources:
                    code = s.get("doc_code") or s.get("title", "")
                    page = s.get("page", "")
                    parts.append(f"[{s.get('n', '?')}] {code}" + (f" p.{page}" if page else ""))
                sp.add_run(", ".join(parts)).font.size = Pt(9)

        doc.add_paragraph()  # blank line between messages

    doc.save(str(output_path))
