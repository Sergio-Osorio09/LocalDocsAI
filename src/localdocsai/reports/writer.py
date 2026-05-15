"""High-level report writer — generates .docx from a filled template."""

from __future__ import annotations

from pathlib import Path

from localdocsai.reports.template import TemplateField, fill_and_save


def write_docx(
    template_path: Path,
    fields: list[TemplateField],
    output_path: Path,
) -> None:
    """Fill *template_path* with *fields* values and save to *output_path*."""
    fill_and_save(template_path, fields, output_path)
