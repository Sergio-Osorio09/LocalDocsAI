"""Markdown → HTML conversion for QTextBrowser message rendering.

No Qt imports — importable in tests without PySide6.
"""

from __future__ import annotations

import re


def markdown_to_html(text: str) -> str:
    """Convert a subset of Markdown to HTML suitable for QTextBrowser."""
    lines = text.split("\n")
    output: list[str] = []
    in_code_block = False
    code_lines: list[str] = []

    for line in lines:
        if line.startswith("```"):
            if in_code_block:
                code_html = "\n".join(html_escape(ln) for ln in code_lines)
                output.append(f"<pre><code>{code_html}</code></pre>")
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue
        if in_code_block:
            code_lines.append(line)
            continue

        if line.startswith("> "):
            output.append(f"<blockquote>{inline(line[2:])}</blockquote>")
            continue

        if line.startswith("### "):
            output.append(f"<h3>{inline(line[4:])}</h3>")
            continue
        if line.startswith("## "):
            output.append(f"<h2>{inline(line[3:])}</h2>")
            continue
        if line.startswith("# "):
            output.append(f"<h1>{inline(line[2:])}</h1>")
            continue

        if line.startswith("- ") or line.startswith("* "):
            output.append(f"<li>{inline(line[2:])}</li>")
            continue

        if not line.strip():
            output.append("<br/>")
            continue

        output.append(f"<p style='margin:2px 0'>{inline(line)}</p>")

    return "\n".join(output)


def inline(text: str) -> str:
    """Apply inline markdown transformations."""
    text = html_escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(\d+)\]", r'<a href="cite:\1" class="cite">[\1]</a>', text)
    return text


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
