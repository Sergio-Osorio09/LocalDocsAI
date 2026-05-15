"""Tests for reports.generator — autofill heuristics."""

from __future__ import annotations

from datetime import date

import pytest

from localdocsai.reports.generator import _build_synthesis, _fill_field, autofill
from localdocsai.reports.template import TemplateField


def _make_field(sem: str) -> TemplateField:
    return TemplateField(
        paragraph_idx=0,
        pattern="[X]",
        context="ctx",
        label="Label",
        semantic_type=sem,
    )


# ---------------------------------------------------------------------------
# _fill_field
# ---------------------------------------------------------------------------


def test_fill_date_returns_today() -> None:
    val = _fill_field("date", [], [], "")
    assert val == date.today().strftime("%d/%m/%Y")


def test_fill_title_returns_chat_title() -> None:
    assert _fill_field("title", [], [], "Mi Proyecto") == "Mi Proyecto"


def test_fill_topic_truncates_first_user_msg() -> None:
    long_msg = "A" * 200
    result = _fill_field("topic", [long_msg], [], "")
    assert len(result) <= 120


def test_fill_objective_returns_full_first_user_msg() -> None:
    msg = "¿Cuál es la normativa vigente?"
    assert _fill_field("objective", [msg], [], "") == msg


def test_fill_synthesis_with_pairs() -> None:
    result = _fill_field(
        "synthesis",
        ["Pregunta 1", "Pregunta 2"],
        ["Respuesta 1", "Respuesta 2"],
        "",
    )
    assert "Consulta 1" in result
    assert "Consulta 2" in result
    assert "Respuesta 1" in result


def test_fill_unknown_returns_empty() -> None:
    assert _fill_field("unknown", ["q"], ["a"], "title") == ""


def test_fill_topic_no_messages() -> None:
    assert _fill_field("topic", [], [], "") == ""


# ---------------------------------------------------------------------------
# autofill
# ---------------------------------------------------------------------------


def test_autofill_fills_all_fields() -> None:
    fields = [_make_field("date"), _make_field("title"), _make_field("unknown")]
    messages = [{"role": "user", "text": "q"}, {"role": "assistant", "text": "a"}]
    result = autofill(fields, messages, chat_title="T")

    assert len(result) == 3
    assert result[0].value  # date always filled
    assert result[1].value == "T"
    assert result[2].value == ""  # unknown → empty


def test_autofill_preserves_field_metadata() -> None:
    field = _make_field("date")
    result = autofill([field], [], "")
    assert result[0].paragraph_idx == field.paragraph_idx
    assert result[0].pattern == field.pattern
    assert result[0].label == field.label


# ---------------------------------------------------------------------------
# _build_synthesis
# ---------------------------------------------------------------------------


def test_build_synthesis_empty() -> None:
    assert _build_synthesis([], []) == ""


def test_build_synthesis_one_pair() -> None:
    result = _build_synthesis(["P"], ["R"])
    assert "Consulta 1" in result
    assert "P" in result
    assert "R" in result


def test_build_synthesis_multiple_pairs_separator() -> None:
    result = _build_synthesis(["P1", "P2"], ["R1", "R2"])
    assert "---" in result
    assert "Consulta 2" in result


def test_build_synthesis_truncates_to_shorter_list() -> None:
    result = _build_synthesis(["P1", "P2", "P3"], ["R1"])
    assert "Consulta 2" not in result
