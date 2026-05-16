"""Markdown → HTML conversion for QTextBrowser message rendering.

No Qt imports — importable in tests without PySide6.
"""

from __future__ import annotations

import re


def markdown_to_html(text: str) -> str:
    """Convert a subset of Markdown to HTML suitable for QTextBrowser."""
    lines = text.split("\n")
    raw: list[str] = []  # raw tokens: "ul", "ol", "p:<html>", "h1:<html>", etc.
    in_code_block = False
    code_lines: list[str] = []

    for line in lines:
        if line.startswith("```"):
            if in_code_block:
                code_html = "\n".join(html_escape(ln) for ln in code_lines)
                raw.append(f"pre:{code_html}")
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue
        if in_code_block:
            code_lines.append(line)
            continue

        if line.startswith("> "):
            raw.append(f"bq:{inline(line[2:])}")
            continue

        if line.startswith("### "):
            raw.append(f"h3:{inline(line[4:])}")
            continue
        if line.startswith("## "):
            raw.append(f"h2:{inline(line[3:])}")
            continue
        if line.startswith("# "):
            raw.append(f"h1:{inline(line[2:])}")
            continue

        if line.startswith("- ") or line.startswith("* "):
            raw.append(f"ul:{inline(line[2:])}")
            continue

        num_match = re.match(r"^(\d+)\.\s+(.*)", line)
        if num_match:
            raw.append(f"ol:{inline(num_match.group(2))}")
            continue

        if not line.strip():
            raw.append("br:")
            continue

        raw.append(f"p:{inline(line)}")

    # Second pass: group consecutive ul/ol items into proper list tags
    output: list[str] = []
    i = 0
    while i < len(raw):
        token = raw[i]
        kind, _, content = token.partition(":")

        if kind in ("ul", "ol"):
            tag = "ul" if kind == "ul" else "ol"
            items: list[str] = []
            while i < len(raw) and raw[i].startswith(f"{kind}:"):
                items.append(raw[i].partition(":")[2])
                i += 1
            output.append(f"<{tag}>{''.join(f'<li>{it}</li>' for it in items)}</{tag}>")
            continue

        if kind == "h1":
            output.append(f"<h1>{content}</h1>")
        elif kind == "h2":
            output.append(f"<h2>{content}</h2>")
        elif kind == "h3":
            output.append(f"<h3>{content}</h3>")
        elif kind == "bq":
            output.append(f"<blockquote>{content}</blockquote>")
        elif kind == "pre":
            output.append(f"<pre><code>{content}</code></pre>")
        elif kind == "br":
            output.append("<br/>")
        else:
            output.append(f"<p style='margin:3px 0'>{content}</p>")
        i += 1

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
