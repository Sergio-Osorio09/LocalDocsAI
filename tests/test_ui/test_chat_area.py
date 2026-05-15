"""Tests for chat_area helpers — pure-Python, no display required."""

from __future__ import annotations

# These helpers live in _markdown.py — no PySide6 dependency
from localdocsai.ui._markdown import html_escape as _html_escape
from localdocsai.ui._markdown import inline as _inline
from localdocsai.ui._markdown import markdown_to_html as _markdown_to_html


class TestHtmlEscape:
    def test_ampersand(self) -> None:
        assert _html_escape("a & b") == "a &amp; b"

    def test_less_than(self) -> None:
        assert _html_escape("a < b") == "a &lt; b"

    def test_greater_than(self) -> None:
        assert _html_escape("a > b") == "a &gt; b"

    def test_no_escape_needed(self) -> None:
        assert _html_escape("hello world") == "hello world"

    def test_combined(self) -> None:
        assert _html_escape("<b>a & b</b>") == "&lt;b&gt;a &amp; b&lt;/b&gt;"


class TestInline:
    def test_bold(self) -> None:
        assert "<strong>hello</strong>" in _inline("**hello**")

    def test_italic(self) -> None:
        assert "<em>hello</em>" in _inline("*hello*")

    def test_code(self) -> None:
        assert "<code>x</code>" in _inline("`x`")

    def test_citation_chip(self) -> None:
        result = _inline("[1]")
        assert 'href="cite:1"' in result
        assert "cite" in result

    def test_citation_chip_multiple(self) -> None:
        result = _inline("see [1] and [2]")
        assert 'href="cite:1"' in result
        assert 'href="cite:2"' in result

    def test_html_is_escaped_first(self) -> None:
        result = _inline("a < b")
        assert "&lt;" in result
        assert "<b>" not in result


class TestMarkdownToHtml:
    def test_header_h1(self) -> None:
        assert "<h1>" in _markdown_to_html("# Title")

    def test_header_h2(self) -> None:
        assert "<h2>" in _markdown_to_html("## Section")

    def test_header_h3(self) -> None:
        assert "<h3>" in _markdown_to_html("### Sub")

    def test_blockquote(self) -> None:
        assert "<blockquote>" in _markdown_to_html("> quoted text")

    def test_list_item(self) -> None:
        assert "<li>" in _markdown_to_html("- item one")

    def test_code_block(self) -> None:
        text = "```\ncode here\n```"
        result = _markdown_to_html(text)
        assert "<pre>" in result
        assert "<code>" in result
        assert "code here" in result

    def test_paragraph(self) -> None:
        result = _markdown_to_html("Hello world")
        assert "<p" in result
        assert "Hello world" in result

    def test_empty_line_becomes_br(self) -> None:
        result = _markdown_to_html("")
        assert "<br/>" in result

    def test_bold_in_paragraph(self) -> None:
        result = _markdown_to_html("This is **important**.")
        assert "<strong>important</strong>" in result

    def test_citation_in_paragraph(self) -> None:
        result = _markdown_to_html("See [1] for details.")
        assert 'href="cite:1"' in result
