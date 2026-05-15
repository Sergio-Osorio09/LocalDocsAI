"""Reports package — .docx generation with placeholder-based templates."""

from localdocsai.reports.generator import autofill
from localdocsai.reports.template import TemplateField, detect_fields, fill_and_save
from localdocsai.reports.writer import write_docx

__all__ = [
    "TemplateField",
    "detect_fields",
    "fill_and_save",
    "autofill",
    "write_docx",
]
