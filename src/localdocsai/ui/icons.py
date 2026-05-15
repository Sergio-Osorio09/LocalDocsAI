"""SVG icon renderer for LocalDocsAI UI.

Converts inline SVG path data into QIcon/QPixmap objects using QSvgRenderer.
All icons use a 24x24 viewBox, stroke-based (no fill), strokeWidth=1.6.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# SVG path data for each icon name. Paths use stroke="currentColor".
_SVG_PATHS: dict[str, str] = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "send": '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke-width="1.8"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
    "folders": (
        '<path d="M3 8a2 2 0 0 1 2-2h3l2 2h6a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8z"/>'
        '<path d="M7 6V5a2 2 0 0 1 2-2h4l2 2h4a2 2 0 0 1 2 2v6"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3'
        " 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2"
        " 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7"
        " 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7"
        " 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1"
        ' 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'
    ),
    "sidebar": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    "sidebar-collapse": (
        '<rect x="3" y="4" width="18" height="16" rx="2"/>'
        '<path d="M9 4v16"/><path d="M14 9l-2 3 2 3"/>'
    ),
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
    "close": '<path d="M18 6L6 18M6 6l12 12"/>',
    "check": '<path d="M5 12l5 5L20 7" stroke-width="2.2"/>',
    "file-doc": (
        '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<path d="M14 3v6h6"/><path d="M9 13h6M9 17h4"/>'
    ),
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    "thumbs-up": '<path d="M7 22V11M14 5.5l-2 5.5H4v9h11l4-9V8a2.5 2.5 0 0 0-5 0v-2.5z"/>',
    "thumbs-down": '<path d="M17 2v11M10 18.5l2-5.5h8V4H9L5 13v3a2.5 2.5 0 0 0 5 0v2.5z"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
    "export": (
        '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>'
        '<path d="M16 8l-4-4-4 4"/><path d="M12 4v12"/>'
    ),
    "sources": ('<path d="M4 4h12a4 4 0 0 1 4 4v12"/>' '<path d="M4 4v12a4 4 0 0 0 4 4h12"/>'),
    "sparkle": (
        '<path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z"/>'
        '<path d="M19 14l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>'
    ),
    "attach": '<path d="M21 12.5l-8.5 8.5a5 5 0 0 1-7-7L14 5.5a3.5 3.5 0 1 1 5 5L10.5 19a2 2 0 1 1-2.8-2.8L15 9"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "cpu": (
        '<rect x="5" y="5" width="14" height="14" rx="2"/>'
        '<rect x="9" y="9" width="6" height="6"/>'
        '<path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/>'
    ),
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "eye": '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/>',
    "trash": (
        '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
    ),
    "edit": (
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        '<path d="M18.5 2.5a2.1 2.1 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
    ),
    "pin": '<path d="M12 17v5"/><path d="M9 2h6l-1 7 4 4H6l4-4-1-7z"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3 2"/>',
    "database": (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"/>'
    ),
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "menu": '<path d="M3 12h18M3 6h18M3 18h18"/>',
    "mic": '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3"/>',
}

_SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg"
     width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="{color}"
     stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
  {paths}
</svg>"""


@lru_cache(maxsize=256)
def _make_svg_bytes(name: str, color: str) -> bytes:
    paths = _SVG_PATHS.get(name, '<circle cx="12" cy="12" r="4"/>')
    return _SVG_TEMPLATE.format(color=color, paths=paths).encode()


def icon(name: str, size: int = 16, color: str = "#8892a8") -> QIcon:
    """Render a named SVG icon as a QIcon at the given pixel size."""
    svg_bytes = _make_svg_bytes(name, color)
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


def pixmap(name: str, size: int = 16, color: str = "#8892a8") -> QPixmap:
    """Render a named SVG icon as a QPixmap."""
    svg_bytes = _make_svg_bytes(name, color)
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return px
